import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:sembast/sembast_io.dart';
import 'package:sembast/sembast_memory.dart';

import 'package:fixflow_tech/data/api_client.dart';
import 'package:fixflow_tech/data/local_store.dart';
import 'package:fixflow_tech/data/sync_service.dart';
import 'package:fixflow_tech/models/models.dart';

QueueItem note(
  String id, {
  int request = 1,
  String body = 'Checked the unit',
  DateTime? at,
}) => QueueItem(
  id: id,
  type: QueueType.note,
  requestId: request,
  createdAt: at ?? DateTime.utc(2026, 11, 12, 10),
  body: body,
);

ApiClient apiWith(MockClientHandler handler) => ApiClient(
  baseUrl: 'http://server.test',
  client: MockClient(handler),
  token: 'token',
  orgId: 1,
);

http.Response json(int status, Object body) => http.Response(
  jsonEncode(body),
  status,
  headers: {'content-type': 'application/json'},
);

Map<String, dynamic> errorBody(String code, String message) => {
  'error': {'code': code, 'message': message},
};

void main() {
  late LocalStore store;
  late SyncService sync;

  setUp(() async {
    store = await LocalStore.open(newDatabaseFactoryMemory(), 'test.db');
    sync = SyncService(store);
  });

  tearDown(() => store.close());

  test('the queue and tasks survive an app restart', () async {
    final dir = await Directory.systemTemp.createTemp('fixflow-store-');
    final path = '${dir.path}/app.db';
    var disk = await LocalStore.open(databaseFactoryIo, path);
    await disk.putQueueItem(note('cmd-00000001', body: 'Offline note'));
    await disk.putQueueItem(
      QueueItem(
        id: 'cmd-00000002',
        type: QueueType.photo,
        requestId: 1,
        createdAt: DateTime.utc(2026, 11, 12, 11),
        filePath: '/data/photo.jpg',
        purpose: 'after',
      ),
    );
    await disk.close(); // "the app is killed"

    disk = await LocalStore.open(
      databaseFactoryIo,
      path,
    ); // "the app starts again"
    final queue = await disk.loadQueue();
    expect(queue.map((i) => i.id), ['cmd-00000001', 'cmd-00000002']);
    expect(queue.first.body, 'Offline note');
    expect(queue.last.filePath, '/data/photo.jpg');
    expect(queue.every((i) => i.state == QueueState.pending), isTrue);
    await disk.close();
    await dir.delete(recursive: true);
  });

  test(
    'a delivered note is removed and sent with its stable command id',
    () async {
      await store.putQueueItem(note('cmd-00000001'));
      late Map<String, dynamic> sent;
      final result = await sync.processQueue(
        apiWith((request) async {
          expect(request.url.path, '/api/v1/requests/1/notes');
          expect(request.headers['Authorization'], 'Bearer token');
          expect(request.headers['X-Organization-Id'], '1');
          sent = jsonDecode(request.body) as Map<String, dynamic>;
          return json(201, {'id': 7});
        }),
      );
      expect(result.sent, 1);
      expect(sent['client_command_id'], 'cmd-00000001');
      expect(sent['body'], 'Checked the unit');
      expect(await store.loadQueue(), isEmpty);
    },
  );

  test('a lost response does not duplicate the note: the retry reuses the same command id', () async {
    await store.putQueueItem(note('cmd-00000001'));

    // A fake server that remembers command ids, like the real backend does.
    final stored = <String, String>{};
    var dropNextResponse = true;
    Future<http.Response> server(http.Request request) async {
      final body = jsonDecode(request.body) as Map<String, dynamic>;
      final id = body['client_command_id'] as String;
      final created = !stored.containsKey(id);
      stored.putIfAbsent(id, () => body['body'] as String);
      if (dropNextResponse) {
        dropNextResponse = false;
        throw http.ClientException(
          'connection reset',
        ); // saved, but the phone never heard back
      }
      return json(created ? 201 : 200, {'id': 1});
    }

    final first = await sync.processQueue(apiWith(server));
    expect(first.offline, isTrue);
    expect((await store.loadQueue()).single.attempts, 1); // still queued

    final second = await sync.processQueue(apiWith(server));
    expect(second.sent, 1);
    expect(await store.loadQueue(), isEmpty);
    expect(stored.length, 1, reason: 'exactly one note exists on the server');
  });

  test(
    'going offline stops the round and keeps order and content intact',
    () async {
      await store.putQueueItem(
        note('cmd-00000001', at: DateTime.utc(2026, 11, 12, 10)),
      );
      await store.putQueueItem(
        note('cmd-00000002', at: DateTime.utc(2026, 11, 12, 11)),
      );
      var calls = 0;
      final result = await sync.processQueue(
        apiWith((request) async {
          calls++;
          throw http.ClientException('no route to host');
        }),
      );
      expect(result.offline, isTrue);
      expect(calls, 1, reason: 'no point hammering a dead connection');
      final queue = await store.loadQueue();
      expect(queue.map((i) => i.id), ['cmd-00000001', 'cmd-00000002']);
      expect(queue.first.attempts, 1);
      expect(queue.last.attempts, 0);
    },
  );

  test('a reassigned job becomes a visible conflict and the draft is kept (MOB-07)', () async {
    await store.putQueueItem(
      note('cmd-00000001', request: 1, body: 'Written offline'),
    );
    await store.putQueueItem(
      note('cmd-00000002', request: 2, body: 'Still fine'),
    );
    final result = await sync.processQueue(
      apiWith((request) async {
        if (request.url.path.contains('/requests/1/')) {
          return json(
            409,
            errorBody(
              'assignment_changed',
              'This request is no longer assigned to you',
            ),
          );
        }
        return json(201, {'id': 2});
      }),
    );
    expect(result.conflicts, 1);
    expect(result.sent, 1);

    final queue = await store.loadQueue();
    expect(
      queue,
      hasLength(1),
    ); // only the conflict is left, and it is NOT deleted
    expect(queue.single.state, QueueState.conflict);
    expect(queue.single.conflictCode, 'assignment_changed');
    expect(queue.single.error, contains('no longer assigned'));
    expect(queue.single.body, 'Written offline');

    // conflicts are not retried automatically: the user must decide
    final again = await sync.processQueue(
      apiWith((request) async => json(201, {})),
    );
    expect(again.didAnything, isFalse);
    expect(await store.loadQueue(), hasLength(1));
  });

  test('an expired session keeps the whole queue and asks for a new sign-in (AUTH-04)', () async {
    await store.putQueueItem(note('cmd-00000001'));
    await store.putQueueItem(note('cmd-00000002'));
    final result = await sync.processQueue(
      apiWith(
        (request) async =>
            json(401, errorBody('session_expired', 'Session expired')),
      ),
    );
    expect(result.unauthorized, isTrue);
    expect(await store.loadQueue(), hasLength(2));
  });

  test('a refused item is marked failed with the reason and is not retried by itself', () async {
    await store.putQueueItem(
      QueueItem(
        id: 'cmd-00000009',
        type: QueueType.note,
        requestId: 1,
        createdAt: DateTime.utc(2026, 11, 12),
        body: 'x',
      ),
    );
    final result = await sync.processQueue(
      apiWith(
        (request) async =>
            json(422, errorBody('validation_error', 'Invalid input')),
      ),
    );
    expect(result.failed, 1);
    final item = (await store.loadQueue()).single;
    expect(item.state, QueueState.failed);
    expect(item.error, 'Invalid input');
    var calls = 0;
    await sync.processQueue(
      apiWith((request) async {
        calls++;
        return json(201, {});
      }),
    );
    expect(calls, 0);
  });

  test('a photo is uploaded as multipart with its command id and the local copy is deleted', () async {
    final dir = await Directory.systemTemp.createTemp('fixflow-photo-');
    final file = File('${dir.path}/shot.jpg')
      ..writeAsBytesSync([0xFF, 0xD8, 0xFF, 0xE0, 1, 2, 3]);
    await store.putQueueItem(
      QueueItem(
        id: 'cmd-photo001',
        type: QueueType.photo,
        requestId: 5,
        createdAt: DateTime.utc(2026, 11, 12),
        filePath: file.path,
        purpose: 'after',
      ),
    );

    String? seenBody;
    final result = await sync.processQueue(
      apiWith((request) async {
        expect(request.url.path, '/api/v1/requests/5/attachments');
        expect(
          request.headers['content-type'],
          startsWith('multipart/form-data'),
        );
        seenBody = latin1.decode(request.bodyBytes);
        return json(201, {'id': 3});
      }),
    );

    expect(result.sent, 1);
    expect(seenBody, contains('name="client_command_id"'));
    expect(seenBody, contains('cmd-photo001'));
    expect(seenBody, contains('name="purpose"'));
    expect(seenBody, contains('name="file"'));
    expect(file.existsSync(), isFalse);
    expect(await store.loadQueue(), isEmpty);
    await dir.delete(recursive: true);
  });

  test(
    'a photo whose file disappeared becomes a failed item instead of crashing',
    () async {
      await store.putQueueItem(
        QueueItem(
          id: 'cmd-photo002',
          type: QueueType.photo,
          requestId: 5,
          createdAt: DateTime.utc(2026, 11, 12),
          filePath: '${Directory.systemTemp.path}/does-not-exist.jpg',
        ),
      );
      final result = await sync.processQueue(
        apiWith((request) async => json(201, {})),
      );
      expect(result.failed, 1);
      expect((await store.loadQueue()).single.state, QueueState.failed);
    },
  );

  test('only one sync round runs at a time', () async {
    await store.putQueueItem(note('cmd-00000001'));
    final results = await Future.wait([
      sync.processQueue(
        apiWith((request) async {
          await Future<void>.delayed(const Duration(milliseconds: 50));
          return json(201, {});
        }),
      ),
      sync.processQueue(apiWith((request) async => json(201, {}))),
    ]);
    expect(results.where((r) => r.sent == 1), hasLength(1));
  });
}
