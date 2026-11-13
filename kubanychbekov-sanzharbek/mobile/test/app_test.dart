import 'dart:convert';
import 'dart:io';
import 'dart:ui' show Size;

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:provider/provider.dart';
import 'package:sembast/sembast_memory.dart';
import 'package:timezone/data/latest_10y.dart' as tzdata;

import 'package:fixflow_tech/data/api_client.dart';
import 'package:fixflow_tech/data/local_store.dart';
import 'package:fixflow_tech/i18n.dart';
import 'package:fixflow_tech/main.dart';
import 'package:fixflow_tech/models/models.dart';
import 'package:fixflow_tech/state/app_state.dart';
import 'package:fixflow_tech/ui/materials_screen.dart';

Task sampleTask({
  int id = 28,
  String status = 'SCHEDULED',
  List<String>? actions,
}) => Task(
  assignmentId: 5,
  assignmentStatus: status,
  startAt: DateTime.now().toUtc().add(const Duration(hours: 3)),
  endAt: DateTime.now().toUtc().add(const Duration(hours: 5)),
  timezone: 'Asia/Bishkek',
  requestId: id,
  title: 'Ventilation fan does not work',
  description: 'The extractor fan makes no sound and no air flows out.',
  priority: 'HIGH',
  requestStatus: status,
  allowedActions: actions ?? ['ACCEPTED'],
  categoryName: 'HVAC',
  propertyName: 'Warehouse D',
  propertyAddress: '22 Ankara St, Bishkek',
  customerName: 'Aidar Sultanov',
  updatedAt: DateTime.utc(2026, 11, 12),
);

Session sampleSession() => Session(
  serverUrl: 'http://server.test',
  token: 'token',
  userName: 'Azamat Kenzhebaev',
  email: 'tech2.a@fixflow.test',
  memberships: [
    Membership(
      organizationId: 1,
      organizationName: 'AIT Facility',
      timezone: 'Asia/Bishkek',
      role: 'technician',
    ),
  ],
  orgId: 1,
);

http.Response jsonResponse(int status, Object body) => http.Response(
  jsonEncode(body),
  status,
  headers: {'content-type': 'application/json'},
);

Future<AppState> buildState(
  MockClientHandler handler, {
  bool signedIn = true,
}) async {
  final store = await LocalStore.open(newDatabaseFactoryMemory(), 'app.db');
  if (signedIn) {
    await store.saveSession(sampleSession());
    await store.replaceTasks([
      sampleTask(),
    ], syncedAt: DateTime.utc(2026, 11, 12, 9));
  }
  final state = AppState(
    store: store,
    httpClient: MockClient(handler),
    photosDir: Directory.systemTemp,
    initialLang: 'en',
  );
  return state;
}

Future<void> pumpApp(WidgetTester tester, AppState state) async {
  await tester.runAsync(() => state.init());
  await tester.pumpWidget(
    ChangeNotifierProvider.value(value: state, child: const FixFlowApp()),
  );
  await tester.runAsync(
    () => Future<void>.delayed(const Duration(milliseconds: 50)),
  );
  await tester.pump();
}

/// A tall screen so lazily built list sections below the fold exist in the tree.
void tallScreen(WidgetTester tester) {
  tester.view.physicalSize = const Size(900, 3000);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
}

void main() {
  setUpAll(() async {
    tzdata.initializeTimeZones();
    await initializeDateFormatting();
  });

  group('translations and time', () {
    test('Russian has exactly the same keys as English', () {
      expect(ru.keys.toSet(), en.keys.toSet());
    });

    test('placeholders are filled', () {
      expect(tr('en', 'detail.title', {'id': 28}), 'Request #28');
      expect(tr('ru', 'detail.title', {'id': 28}), 'Заявка #28');
    });

    test('backend error codes map to messages with a safe fallback', () {
      expect(
        trError('en', 'assignment_changed'),
        contains('no longer assigned'),
      );
      expect(trError('en', 'something_unknown'), tr('en', 'err.generic'));
    });

    test(
      'times are shown in the organization timezone, not the phone zone',
      () {
        final instant = DateTime.utc(
          2026,
          11,
          16,
          4,
          0,
        ); // 10:00 in Bishkek (UTC+6)
        expect(formatWhen(instant, 'Asia/Bishkek', 'en'), '16 Nov, 10:00');
        expect(
          formatWhen(instant, 'Asia/Tashkent', 'en'),
          '16 Nov, 09:00',
        ); // UTC+5
        expect(
          localDay(DateTime.utc(2026, 11, 16, 19, 30), 'Asia/Bishkek'),
          '2026-11-17',
        );
      },
    );
  });

  group('signing in', () {
    http.Response server(
      http.Request request, {
      required List<Map<String, Object?>> memberships,
    }) {
      if (request.url.path.endsWith('/auth/login')) {
        return jsonResponse(200, {
          'access_token': 'tok',
          'token_type': 'bearer',
        });
      }
      if (request.url.path.endsWith('/me')) {
        return jsonResponse(200, {
          'id': 1,
          'email': 'tech1.a@fixflow.test',
          'full_name': 'Erlan',
          'memberships': memberships,
        });
      }
      return jsonResponse(200, []);
    }

    Map<String, Object?> membership(int id, String role) => {
      'organization_id': id,
      'organization_name': 'Org $id',
      'timezone': 'Asia/Bishkek',
      'role': role,
    };

    test('only technician memberships are kept and one organization is chosen automatically', () async {
      final state = await buildState(
        (r) async => server(
          r,
          memberships: [membership(1, 'technician'), membership(2, 'customer')],
        ),
        signedIn: false,
      );
      await state.init();
      final outcome = await state.login(
        'http://server.test/',
        'tech1.a@fixflow.test',
        'pw',
      );
      expect(outcome, LoginOutcome.signedIn);
      expect(state.session!.memberships.map((m) => m.organizationId), [1]);
      expect(state.session!.orgId, 1);
      expect(
        state.session!.serverUrl,
        'http://server.test',
      ); // trailing slash removed
    });

    test('two technician organizations require an explicit choice', () async {
      final state = await buildState(
        (r) async => server(
          r,
          memberships: [
            membership(1, 'technician'),
            membership(2, 'technician'),
          ],
        ),
        signedIn: false,
      );
      await state.init();
      expect(
        await state.login('http://server.test', 'a@b.c', 'pw'),
        LoginOutcome.needsOrganization,
      );
      expect(state.needsOrganization, isTrue);
    });

    test('an account without a technician role is refused', () async {
      final state = await buildState(
        (r) async => server(r, memberships: [membership(1, 'customer')]),
        signedIn: false,
      );
      await state.init();
      expect(
        () => state.login('http://server.test', 'a@b.c', 'pw'),
        throwsA(
          isA<ApiException>().having(
            (e) => e.code,
            'code',
            'no_technician_role',
          ),
        ),
      );
    });

    test(
      'another person signing in never inherits the previous queue',
      () async {
        final state = await buildState(
          (r) async => server(r, memberships: [membership(1, 'technician')]),
        );
        await state.init();
        await state.store.putQueueItem(
          QueueItem(
            id: 'cmd-previous1',
            type: QueueType.note,
            requestId: 1,
            createdAt: DateTime.utc(2026, 11, 12),
            body: 'belongs to the previous user',
          ),
        );
        // the saved session is tech2.a; the server now answers as tech1.a
        await state.login('http://server.test', 'tech1.a@fixflow.test', 'pw');
        expect(await state.store.loadQueue(), isEmpty);
        expect(await state.store.loadTasks(), isEmpty);
      },
    );
  });

  group('materials and estimate (online only)', () {
    test('money is formatted from whole tyiyn without floating point', () {
      expect(formatKgs(0), '0.00 KGS');
      expect(formatKgs(123456), '1 234.56 KGS');
      expect(formatKgs(5), '0.05 KGS');
      expect(formatKgs(100000000), '1 000 000.00 KGS');
    });

    test(
      'quantity input accepts a comma, rejects zero, text and 4 decimals',
      () {
        expect(parseQuantity('1,5'), '1.5');
        expect(parseQuantity(' 2 '), '2');
        expect(parseQuantity('0'), isNull);
        expect(parseQuantity('-1'), isNull);
        expect(parseQuantity('abc'), isNull);
        expect(parseQuantity('1.2345'), isNull);
      },
    );

    test(
      'write-off sends the item, quantity and the same command id',
      () async {
        final bodies = <Map<String, dynamic>>[];
        final state = await buildState((r) async {
          if (r.method == 'POST' &&
              r.url.path.endsWith('/requests/28/materials')) {
            bodies.add(jsonDecode(r.body) as Map<String, dynamic>);
            return jsonResponse(201, {});
          }
          return jsonResponse(200, []);
        });
        await state.init();
        await state.useMaterial(sampleTask(), 7, '2.5', 'cmd-material-1');
        expect(bodies, [
          {
            'item_id': 7,
            'quantity': '2.5',
            'client_command_id': 'cmd-material-1',
          },
        ]);
      },
    );

    test(
      'insufficient stock from the server is passed on with its code',
      () async {
        final state = await buildState((r) async {
          if (r.method == 'POST') {
            return jsonResponse(409, {
              'error': {'code': 'insufficient_stock', 'message': 'Not enough'},
            });
          }
          return jsonResponse(200, []);
        });
        await state.init();
        await expectLater(
          state.useMaterial(sampleTask(), 7, '99', 'cmd-material-2'),
          throwsA(
            isA<ApiException>().having(
              (e) => e.code,
              'code',
              'insufficient_stock',
            ),
          ),
        );
        expect(
          trError('en', 'insufficient_stock'),
          isNot(tr('en', 'err.generic')),
        );
        expect(
          trError('ru', 'work_not_in_progress'),
          isNot(tr('ru', 'err.generic')),
        );
      },
    );

    test('only an APPROVED estimate total is returned', () async {
      final state = await buildState((r) async {
        if (r.url.path.endsWith('/requests/28/estimates')) {
          return jsonResponse(200, [
            {'status': 'AWAITING_APPROVAL', 'total_cents': 111},
            {'status': 'APPROVED', 'total_cents': 450000},
          ]);
        }
        return jsonResponse(200, []);
      });
      await state.init();
      expect(await state.approvedEstimateCents(28), 450000);
    });

    test('no approved estimate gives null', () async {
      final state = await buildState((r) async => jsonResponse(200, []));
      await state.init();
      expect(await state.approvedEstimateCents(28), isNull);
    });
  });

  group('login screen layout', () {
    for (final width in [320.0, 360.0, 390.0]) {
      testWidgets(
        'header does not overflow on a ${width.toInt()} px phone in Russian',
        (tester) async {
          tester.view.physicalSize = Size(width, 800);
          tester.view.devicePixelRatio = 1;
          addTearDown(tester.view.reset);
          final state = (await tester.runAsync(
            () =>
                buildState((r) async => jsonResponse(200, []), signedIn: false),
          ))!;
          await tester.runAsync(() => state.setLang('ru'));
          await pumpApp(tester, state);
          expect(find.text('FixFlow'), findsOneWidget);
          expect(
            tester.takeException(),
            isNull,
          ); // an overflow would be reported here
        },
      );
    }
  });

  group('offline behaviour', () {
    testWidgets(
      'cached tasks are shown without a connection, with an offline banner',
      (tester) async {
        final state = (await tester.runAsync(
          () => buildState((r) async => throw http.ClientException('offline')),
        ))!;
        await pumpApp(tester, state);

        expect(find.text('Ventilation fan does not work'), findsOneWidget);
        expect(find.textContaining('#28'), findsWidgets);
        expect(find.textContaining('Offline mode'), findsOneWidget);
        expect(state.online, isFalse);
      },
    );

    testWidgets(
      'status changes are disabled offline and explain why (MOB-08)',
      (tester) async {
        tallScreen(tester);
        final state = (await tester.runAsync(
          () => buildState((r) async => throw http.ClientException('offline')),
        ))!;
        await pumpApp(tester, state);

        await tester.tap(find.text('Ventilation fan does not work'));
        await tester.pumpAndSettle();

        expect(find.text('Accept task'), findsOneWidget);
        expect(find.textContaining('needs a connection'), findsOneWidget);
        // ...but writing notes and photos stays possible offline for an assigned task (MOB-05)
        expect(find.text('Add note'), findsOneWidget);
        expect(find.text('Add photo'), findsOneWidget);
      },
    );

    testWidgets(
      'an active task offers notes and photos offline and the queue counts them',
      (tester) async {
        tallScreen(tester);
        final state = (await tester.runAsync(
          () => buildState((r) async => throw http.ClientException('offline')),
        ))!;
        await tester.runAsync(
          () => state.store.replaceTasks([
            sampleTask(status: 'IN_PROGRESS', actions: ['BLOCKED']),
          ], syncedAt: DateTime.utc(2026, 11, 12, 9)),
        );
        await pumpApp(tester, state);

        await tester.tap(find.text('Ventilation fan does not work'));
        await tester.pumpAndSettle();
        expect(find.text('Add note'), findsOneWidget);
        expect(find.text('Add photo'), findsOneWidget);

        await tester.runAsync(
          () => state.enqueueNote(28, 'Pressure is low', internal: false),
        );
        await tester.pump();
        expect(state.queue, hasLength(1));
        expect(
          find.text('Pressure is low'),
          findsOneWidget,
        ); // shown as "waiting to sync"
      },
    );

    testWidgets(
      'a conflict in the queue is shown with its reason and a delete decision',
      (tester) async {
        final state = (await tester.runAsync(
          () => buildState((r) async => throw http.ClientException('offline')),
        ))!;
        await tester.runAsync(
          () => state.store.putQueueItem(
            QueueItem(
              id: 'cmd-conflict1',
              type: QueueType.note,
              requestId: 28,
              createdAt: DateTime.utc(2026, 11, 12, 10),
              body: 'Written while offline',
              state: QueueState.conflict,
              error: 'This request is no longer assigned to you',
              conflictCode: 'assignment_changed',
            ),
          ),
        );
        await pumpApp(tester, state);

        await tester.tap(find.text('Queue').last);
        await tester.pumpAndSettle();
        expect(find.text('Conflict'), findsOneWidget);
        expect(find.text('Written while offline'), findsOneWidget);
        expect(find.textContaining('no longer assigned'), findsOneWidget);

        await tester.tap(find.text('Delete'));
        await tester.pumpAndSettle();
        expect(
          find.text('Delete this item?'),
          findsOneWidget,
        ); // explicit confirmation first
        expect(state.queue, hasLength(1));
      },
    );
  });
}
