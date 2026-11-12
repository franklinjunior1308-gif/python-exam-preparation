// Live integration test: the real Flutter app code against the REAL FastAPI + PostgreSQL stack.
//
// Skipped unless FIXFLOW_API is set (the normal `flutter test` run stays offline). Run:
//   $env:FIXFLOW_API="http://localhost:8000"; flutter test test/live --timeout=120s
// Needs the demo data (`python -m app.seed`) and a technician with at least one active task.
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:image/image.dart' as img;
import 'package:sembast/sembast_memory.dart';

import 'package:fixflow_tech/data/api_client.dart';
import 'package:fixflow_tech/data/local_store.dart';
import 'package:fixflow_tech/models/models.dart';
import 'package:fixflow_tech/state/app_state.dart';

final String? apiUrl = Platform.environment['FIXFLOW_API'];

/// Delegates to the real client but loses the response of the first matching POST AFTER the
/// server has processed it: the exact "phone never heard back" situation (MOB-06).
class LoseFirstResponse extends http.BaseClient {
  LoseFirstResponse(this._inner, this.matches);

  final http.Client _inner;
  final bool Function(http.BaseRequest) matches;
  bool dropped = false;
  int serverCalls = 0;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final response = await _inner.send(request);
    if (matches(request)) {
      serverCalls++;
      if (!dropped) {
        dropped = true;
        await response.stream.drain<void>();
        throw http.ClientException('connection reset after the server answered');
      }
    }
    return response;
  }
}

List<int> tinyPng() {
  final image = img.Image(width: 24, height: 16);
  img.fill(image, color: img.ColorRgb8(30, 120, 220));
  return img.encodePng(image);
}

void main() {
  final skip = apiUrl == null ? 'set FIXFLOW_API to run against the live backend' : false;

  test('technician: sign in, load tasks, queue offline work, sync exactly once', () async {
    final tmp = await Directory.systemTemp.createTemp('fixflow-live-');
    final store = await LocalStore.open(newDatabaseFactoryMemory(), 'live.db');
    final base = http.Client();
    final flaky = LoseFirstResponse(base, (r) => r.method == 'POST' && r.url.path.endsWith('/notes'));
    final state = AppState(
      store: store,
      httpClient: flaky,
      photosDir: Directory('${tmp.path}/photos'),
      defaultServerUrl: apiUrl!,
    );
    await state.init();

    // 1) real sign-in against /auth/login + /me
    final outcome = await state.login(apiUrl!, 'tech2.a@fixflow.test', 'Demo-2345!');
    expect(outcome, LoginOutcome.signedIn);
    expect(state.session!.memberships.single.role, 'technician');

    // 2) real task list from /my/tasks, cached in the local database
    // sign-in already started a refresh in the background: wait for it, then refresh again
    for (var i = 0; i < 100 && (state.refreshing || state.tasks.isEmpty); i++) {
      await Future<void>.delayed(const Duration(milliseconds: 100));
    }
    await state.refresh();
    expect(state.online, isTrue);
    expect(state.tasks, isNotEmpty);
    expect((await store.loadTasks()).length, state.tasks.length); // survives a restart
    final task = state.tasks.firstWhere((t) => t.isActive);
    expect(task.propertyAddress, isNotEmpty);

    // 3) a note written "offline": queued first, then delivered with a stable command id
    final marker = 'live-test ${DateTime.now().microsecondsSinceEpoch}';
    await state.enqueueNote(task.requestId, marker, internal: true);
    await Future<void>.delayed(const Duration(seconds: 3)); // background sync after the enqueue
    // the first answer was lost, so the item is still queued
    expect(state.queue.where((i) => i.body == marker), hasLength(1));
    expect(flaky.dropped, isTrue);

    // 4) retry (same command id): the server returns the ORIGINAL note, nothing is duplicated
    final result = await state.runSync();
    expect(result.sent, greaterThanOrEqualTo(1));
    expect(state.queue.where((i) => i.body == marker), isEmpty);
    final notes = await state.loadNotes(task.requestId);
    expect(notes.where((n) => n.body == marker), hasLength(1));
    expect(notes.firstWhere((n) => n.body == marker).visibility, 'internal');

    // 5) a photo from the queue is uploaded as multipart and the local copy is removed
    final source = File('${tmp.path}/shot.png')..writeAsBytesSync(tinyPng());
    final before = (await state.loadAttachments(task.requestId)).length;
    await state.enqueuePhoto(task.requestId, source.path, purpose: 'after');
    final queued = state.queue.firstWhere((i) => i.type == QueueType.photo);
    await Future<void>.delayed(const Duration(seconds: 3));
    await state.runSync();
    final after = await state.loadAttachments(task.requestId);
    expect(after.length, before + 1);
    expect(File(queued.filePath!).existsSync(), isFalse);

    // 6) the uploaded photo is downloadable only with the session (authorized endpoint)
    final client = state.api!;
    final res = await base.get(client.fileUri(after.last.id), headers: client.imageHeaders);
    expect(res.statusCode, 200);
    expect(res.headers['content-type'], 'image/png');
    final anonymous = await base.get(client.fileUri(after.last.id));
    expect(anonymous.statusCode, 401);

    // 7) a wrong state change is refused by the server and surfaced as an error, not a success
    await expectLater(
      state.transition(task, 'CLOSED'),
      throwsA(isA<ApiException>().having((e) => e.status, 'status', anyOf(403, 409))),
    );
    await tmp.delete(recursive: true);
  }, skip: skip);

  test('an invalid password is a clean error and nothing is stored', () async {
    final store = await LocalStore.open(newDatabaseFactoryMemory(), 'live2.db');
    final state = AppState(
      store: store,
      httpClient: http.Client(),
      photosDir: Directory.systemTemp,
    );
    await state.init();
    await expectLater(
      state.login(apiUrl!, 'tech2.a@fixflow.test', 'wrong-password'),
      throwsA(isA<ApiException>().having((e) => e.code, 'code', 'invalid_credentials')),
    );
    expect(state.session, isNull);
    expect(await store.loadSession(), isNull); // nothing was saved
  }, skip: skip);
}
