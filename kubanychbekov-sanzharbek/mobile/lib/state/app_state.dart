import 'dart:async';
import 'dart:io';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:path/path.dart' as p;

import '../data/api_client.dart';
import '../data/local_store.dart';
import '../data/sync_service.dart';
import '../models/models.dart';

enum LoginOutcome { signedIn, needsOrganization }

/// The single source of truth for the UI (state management: provider + ChangeNotifier).
///
/// Reading is always local-first: tasks and the queue come from the phone's database, and the
/// network only refreshes them. That is what keeps the app usable offline (MOB-03, MOB-04).
class AppState extends ChangeNotifier {
  AppState({
    required this.store,
    required this.httpClient,
    required this.photosDir,
    this.defaultServerUrl = 'http://10.0.2.2:8000',
    String initialLang = 'en',
  }) : lang = initialLang;

  final LocalStore store;
  final http.Client httpClient;
  final Directory photosDir;
  final String defaultServerUrl;
  late final SyncService sync = SyncService(store);

  bool ready = false;
  Session? session;
  List<Task> tasks = [];
  List<QueueItem> queue = [];
  List<NotificationItem> notifications = [];
  DateTime? lastSync;
  String lang;

  /// Last known connectivity: true after a successful call, false after a network failure.
  bool online = true;
  bool refreshing = false;
  bool syncing = false;

  /// One-shot message for the UI (snack bar), cleared by the UI after showing it.
  String? notice;

  Timer? _timer;

  bool get signedIn => session != null && !session!.needsLogin;
  bool get needsOrganization => signedIn && session!.orgId == null;
  Membership? get membership => session?.membership;
  int get unreadNotifications => notifications.where((n) => n.unread).length;
  int get waitingCount =>
      queue.where((i) => i.state == QueueState.pending).length;
  int get attentionCount =>
      queue.where((i) => i.state != QueueState.pending).length;

  ApiClient? get api {
    final s = session;
    if (s == null) return null;
    return ApiClient(
      baseUrl: s.serverUrl,
      client: httpClient,
      token: s.token,
      orgId: s.orgId,
    );
  }

  // ------------------------------------------------------------------ start-up
  Future<void> init() async {
    session = await store.loadSession();
    tasks = await store.loadTasks();
    queue = await store.loadQueue();
    lastSync = await store.lastSync();
    lang = await store.getPref('lang') ?? lang;
    ready = true;
    notifyListeners();
    if (signedIn && session!.orgId != null) unawaited(refresh());
  }

  /// Periodic retry while the app is open: refresh tasks and deliver the queue.
  void startAutoSync({Duration every = const Duration(seconds: 25)}) {
    _timer?.cancel();
    _timer = Timer.periodic(every, (_) {
      if (signedIn && session!.orgId != null) unawaited(refresh());
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> setLang(String value) async {
    lang = value;
    await store.setPref('lang', value);
    notifyListeners();
  }

  // ------------------------------------------------------------------ sign in / out
  Future<String> savedServerUrl() async =>
      await store.getPref('server') ?? defaultServerUrl;

  Future<LoginOutcome> login(
    String serverUrl,
    String email,
    String password,
  ) async {
    final url = serverUrl.trim().replaceAll(RegExp(r'/+$'), '');
    final anonymous = ApiClient(baseUrl: url, client: httpClient);
    final auth = await anonymous.post(
      'auth/login',
      body: {'email': email.trim(), 'password': password},
    ) as Map<String, dynamic>;
    final token = auth['access_token'] as String;

    final authed = ApiClient(baseUrl: url, client: httpClient, token: token);
    final me = await authed.get('me') as Map<String, dynamic>;
    final memberships = (me['memberships'] as List)
        .map((e) => Membership.fromJson(Map<String, dynamic>.from(e as Map)))
        .where((m) => m.role == 'technician') // this app is for technicians
        .toList();
    if (memberships.isEmpty) {
      throw ApiException(403, 'no_technician_role', 'No technician role');
    }

    final previous = session;
    if (previous != null && previous.email != me['email']) {
      await _wipeLocalWork(); // a different person: never mix their data (privacy)
    }
    await store.setPref('server', url);
    session = Session(
      serverUrl: url,
      token: token,
      userName: me['full_name'] as String,
      email: me['email'] as String,
      memberships: memberships,
      orgId: memberships.length == 1 ? memberships.first.organizationId : null,
    );
    await store.saveSession(session!);
    notifyListeners();
    if (session!.orgId != null) unawaited(refresh());
    return session!.orgId == null
        ? LoginOutcome.needsOrganization
        : LoginOutcome.signedIn;
  }

  Future<void> selectOrganization(int organizationId) async {
    final current = session;
    if (current == null) return;
    if (current.orgId != null && current.orgId != organizationId) {
      await store.clearTasks(); // never show the previous organization's tasks
      tasks = [];
      notifications = [];
    }
    session = current.copyWith(orgId: organizationId);
    await store.saveSession(session!);
    notifyListeners();
    unawaited(refresh());
  }

  Future<void> logout() async {
    try {
      await api?.post('auth/logout');
    } on ApiException {
      // offline sign-out is fine: the session simply expires on the server
    }
    session = null;
    await store.clearSession();
    notifications = [];
    notifyListeners();
  }

  Future<void> _wipeLocalWork() async {
    for (final item in await store.loadQueue()) {
      await store.deleteQueueItem(item.id);
      _deleteFile(item.filePath);
    }
    await store.clearTasks();
    tasks = [];
    queue = [];
  }

  // ------------------------------------------------------------------ refresh & sync
  void _markOnline(bool value) {
    if (online != value) online = value;
  }

  Future<void> _handleAuth(ApiException e) async {
    if (e.isUnauthorized && session != null) {
      // keep tasks and the queue; only the token is no longer valid (AUTH-04)
      session = session!.copyWith(needsLogin: true);
      await store.saveSession(session!);
    }
  }

  Future<void> refresh() async {
    final client = api;
    if (client == null || session?.orgId == null || refreshing) return;
    refreshing = true;
    notifyListeners();
    try {
      final raw = await client.get('my/tasks') as List;
      final fresh = raw
          .map((e) => Task.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList();
      final now = DateTime.now().toUtc();
      await store.replaceTasks(fresh, syncedAt: now);
      tasks = await store.loadTasks();
      lastSync = now;
      _markOnline(true);
      await runSync(quiet: true);
      unawaited(loadNotifications());
    } on ApiException catch (e) {
      if (e.isNetwork) {
        _markOnline(false);
      } else {
        await _handleAuth(e);
        if (!e.isUnauthorized) notice = e.code;
      }
    } finally {
      refreshing = false;
      notifyListeners();
    }
  }

  Future<SyncResult> runSync({bool quiet = false}) async {
    final client = api;
    if (client == null || session!.needsLogin) return const SyncResult();
    syncing = true;
    notifyListeners();
    try {
      final result = await sync.processQueue(client);
      queue = await store.loadQueue();
      if (result.offline) _markOnline(false);
      if (result.unauthorized && session != null) {
        session = session!.copyWith(needsLogin: true);
        await store.saveSession(session!);
      }
      if (!quiet && result.sent > 0) notice = 'synced:${result.sent}';
      if (result.conflicts > 0) notice = 'conflicts:${result.conflicts}';
      if (result.sent > 0 && !result.offline) {
        // tasks may have moved on while we were delivering: refresh quietly once
        unawaited(_refreshTasksOnly());
      }
      return result;
    } finally {
      syncing = false;
      notifyListeners();
    }
  }

  Future<void> _refreshTasksOnly() async {
    final client = api;
    if (client == null) return;
    try {
      final raw = await client.get('my/tasks') as List;
      final fresh = raw
          .map((e) => Task.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList();
      await store.replaceTasks(fresh, syncedAt: DateTime.now().toUtc());
      tasks = await store.loadTasks();
      notifyListeners();
    } on ApiException {
      // keep what we have
    }
  }

  // ------------------------------------------------------------------ offline-capable work
  static final Random _random = Random.secure();

  /// A stable, hard-to-collide command id: sent on every attempt so retries are idempotent.
  static String newCommandId() {
    final bytes = List<int>.generate(16, (_) => _random.nextInt(256));
    return bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
  }

  Future<void> enqueueNote(
    int requestId,
    String body, {
    required bool internal,
  }) async {
    final item = QueueItem(
      id: newCommandId(),
      type: QueueType.note,
      requestId: requestId,
      createdAt: DateTime.now().toUtc(),
      body: body.trim(),
      visibility: internal ? 'internal' : 'public',
    );
    await store.putQueueItem(item);
    queue = await store.loadQueue();
    notifyListeners();
    unawaited(runSync(quiet: true));
  }

  /// Copies the picked photo into app storage first: the picker's temp file may be cleaned up
  /// before the connection comes back (MOB-04: the queue must survive restarts).
  Future<void> enqueuePhoto(
    int requestId,
    String sourcePath, {
    required String purpose,
  }) async {
    await photosDir.create(recursive: true);
    final id = newCommandId();
    final ext = p.extension(sourcePath).toLowerCase();
    final target = p.join(photosDir.path, '$id${ext.isEmpty ? '.jpg' : ext}');
    await File(sourcePath).copy(target);
    final item = QueueItem(
      id: id,
      type: QueueType.photo,
      requestId: requestId,
      createdAt: DateTime.now().toUtc(),
      filePath: target,
      purpose: purpose,
    );
    await store.putQueueItem(item);
    queue = await store.loadQueue();
    notifyListeners();
    unawaited(runSync(quiet: true));
  }

  Future<void> retryItem(String id) async {
    final item = queue.firstWhere((i) => i.id == id);
    await store.putQueueItem(
      QueueItem(
        id: item.id,
        type: item.type,
        requestId: item.requestId,
        createdAt: item.createdAt,
        body: item.body,
        visibility: item.visibility,
        filePath: item.filePath,
        purpose: item.purpose,
        attempts: item.attempts,
      ),
    ); // back to pending, error cleared
    queue = await store.loadQueue();
    notifyListeners();
    await runSync();
  }

  /// Deleting is always an explicit user decision (MOB-07).
  Future<void> discardItem(String id) async {
    final item = queue.firstWhere((i) => i.id == id);
    await store.deleteQueueItem(id);
    _deleteFile(item.filePath);
    queue = await store.loadQueue();
    notifyListeners();
  }

  void _deleteFile(String? path) {
    if (path == null) return;
    final file = File(path);
    if (file.existsSync()) file.deleteSync();
  }

  List<QueueItem> queueFor(int requestId) =>
      queue.where((i) => i.requestId == requestId).toList();

  // ------------------------------------------------------------------ online-only actions (MOB-08)
  Future<void> _online(Future<void> Function(ApiClient api) call) async {
    final client = api;
    if (client == null) {
      throw ApiException(401, 'session_expired', 'Not signed in');
    }
    try {
      await call(client);
      _markOnline(true);
    } on ApiException catch (e) {
      if (e.isNetwork) _markOnline(false);
      await _handleAuth(e);
      notifyListeners();
      rethrow;
    }
    await _refreshTasksOnly();
  }

  Future<void> transition(Task task, String target, {String? reason}) =>
      _online((api) async {
        await api.post(
          'requests/${task.requestId}/transitions',
          body: {'to_status': target, 'reason': ?reason},
        );
      });

  Future<void> decline(Task task, {String? reason}) => _online((api) async {
    await api.post(
      'assignments/${task.assignmentId}/decline',
      body: {'reason': reason},
    );
  });

  Future<void> complete(Task task, String summary, String commandId) =>
      _online((api) async {
        await api.post(
          'requests/${task.requestId}/complete',
          body: {'summary': summary.trim(), 'client_command_id': commandId},
        );
      });

  // ------------------------------------------------------------------ read-through helpers
  Future<List<RemoteNote>> loadNotes(int requestId) async {
    final raw = await api!.get('requests/$requestId/notes') as List;
    return raw
        .map((e) => RemoteNote.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
  }

  Future<List<RemoteAttachment>> loadAttachments(int requestId) async {
    final raw = await api!.get('requests/$requestId/attachments') as List;
    return raw
        .map(
          (e) => RemoteAttachment.fromJson(Map<String, dynamic>.from(e as Map)),
        )
        .toList();
  }

  Future<List<InventoryItem>> loadInventory() async {
    final raw = await api!.get('inventory') as List;
    return raw
        .map((e) => InventoryItem.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
  }

  Future<List<MaterialUse>> loadUsages(int requestId) async {
    final raw = await api!.get('requests/$requestId/materials') as List;
    return raw
        .map((e) => MaterialUse.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
  }

  /// Total of the customer-approved estimate in tyiyn, or null when none is approved (EST-05).
  Future<int?> approvedEstimateCents(int requestId) async {
    final raw = await api!.get('requests/$requestId/estimates') as List;
    for (final e in raw) {
      final map = Map<String, dynamic>.from(e as Map);
      if (map['status'] == 'APPROVED') return map['total_cents'] as int;
    }
    return null;
  }

  /// Writes material off a request. Online only (MOB-08); the command id makes a retry harmless.
  Future<void> useMaterial(
    Task task,
    int itemId,
    String quantity,
    String commandId,
  ) => _online((api) async {
    await api.post(
      'requests/${task.requestId}/materials',
      body: {
        'item_id': itemId,
        'quantity': quantity,
        'client_command_id': commandId,
      },
    );
  });

  Future<void> loadNotifications() async {
    final client = api;
    if (client == null || session?.orgId == null) return;
    try {
      final raw = await client.get('notifications') as List;
      notifications = raw
          .map(
            (e) =>
                NotificationItem.fromJson(Map<String, dynamic>.from(e as Map)),
          )
          .toList();
      notifyListeners();
    } on ApiException {
      // the inbox is simply stale until the next successful refresh
    }
  }

  Future<void> markAllRead() => _online((api) async {
    await api.post('notifications/read-all');
    await loadNotifications();
  });

  void clearNotice() {
    notice = null;
  }
}
