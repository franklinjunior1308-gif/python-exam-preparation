import 'package:sembast/sembast.dart';

import '../models/models.dart';

/// Persistent local storage (sembast: a pure-Dart document database kept in a file).
///
/// It holds the session, the last synchronized tasks and the offline queue, so a restart of the
/// app loses nothing (MOB-04). The same class runs on the phone and in unit tests.
class LocalStore {
  LocalStore(this._db);

  final Database _db;

  final StoreRef<String, Object?> _meta = StoreRef<String, Object?>('meta');
  final StoreRef<int, Map<String, Object?>> _tasks = intMapStoreFactory.store('tasks');
  final StoreRef<String, Map<String, Object?>> _queue = stringMapStoreFactory.store('queue');

  static Future<LocalStore> open(DatabaseFactory factory, String path) async =>
      LocalStore(await factory.openDatabase(path));

  Future<void> close() => _db.close();

  // ---- session
  Future<void> saveSession(Session session) =>
      _meta.record('session').put(_db, session.toJson());

  Future<Session?> loadSession() async {
    final raw = await _meta.record('session').get(_db);
    if (raw is! Map) return null;
    return Session.fromJson(Map<String, dynamic>.from(raw));
  }

  Future<void> clearSession() => _meta.record('session').delete(_db);

  // ---- simple preferences
  Future<void> setPref(String key, String? value) async {
    if (value == null) {
      await _meta.record('pref:$key').delete(_db);
    } else {
      await _meta.record('pref:$key').put(_db, value);
    }
  }

  Future<String?> getPref(String key) async => (await _meta.record('pref:$key').get(_db)) as String?;

  // ---- tasks (a snapshot of the last successful sync)
  Future<void> replaceTasks(List<Task> tasks, {required DateTime syncedAt}) async {
    await _db.transaction((txn) async {
      await _tasks.delete(txn);
      for (final task in tasks) {
        await _tasks.record(task.assignmentId).put(txn, task.toJson());
      }
      await _meta.record('last_sync').put(txn, syncedAt.toIso8601String());
    });
  }

  Future<List<Task>> loadTasks() async {
    final records = await _tasks.find(_db);
    final tasks = records.map((r) => Task.fromJson(Map<String, dynamic>.from(r.value))).toList()
      ..sort((a, b) => a.startAt.compareTo(b.startAt));
    return tasks;
  }

  Future<DateTime?> lastSync() async {
    final raw = await _meta.record('last_sync').get(_db);
    return raw is String ? DateTime.parse(raw) : null;
  }

  // ---- offline queue
  Future<void> putQueueItem(QueueItem item) => _queue.record(item.id).put(_db, item.toJson());

  Future<void> deleteQueueItem(String id) => _queue.record(id).delete(_db);

  Future<List<QueueItem>> loadQueue() async {
    final records = await _queue.find(_db);
    final items = records.map((r) => QueueItem.fromJson(Map<String, dynamic>.from(r.value))).toList()
      ..sort((a, b) => a.createdAt.compareTo(b.createdAt));
    return items;
  }

  /// Forget cached data of another user/organization but never the queue.
  Future<void> clearTasks() => _tasks.delete(_db);
}
