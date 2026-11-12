import 'dart:io';
import 'dart:ui' as ui;

import 'package:http/http.dart' as http;
import 'package:intl/date_symbol_data_local.dart';
import 'package:material_ui/material_ui.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:provider/provider.dart';
import 'package:sembast/sembast_io.dart';
import 'package:timezone/data/latest_10y.dart' as tzdata;

import 'data/local_store.dart';
import 'i18n.dart';
import 'state/app_state.dart';
import 'theme.dart';
import 'ui/home_screen.dart';
import 'ui/login_screen.dart';
import 'ui/org_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  tzdata.initializeTimeZones();
  await initializeDateFormatting();

  final docs = await getApplicationDocumentsDirectory();
  final store = await LocalStore.open(
    databaseFactoryIo,
    p.join(docs.path, 'fixflow.db'),
  );
  final deviceLang = ui.PlatformDispatcher.instance.locale.languageCode == 'ru'
      ? 'ru'
      : 'en';

  final state = AppState(
    store: store,
    httpClient: http.Client(),
    photosDir: Directory(p.join(docs.path, 'queued_photos')),
    initialLang: deviceLang,
  );
  await state.init();
  state.startAutoSync();
  runApp(ChangeNotifierProvider.value(value: state, child: const FixFlowApp()));
}

class FixFlowApp extends StatelessWidget {
  const FixFlowApp({super.key});

  @override
  Widget build(BuildContext context) {
    final lang = context.watch<AppState>().lang;
    return MaterialApp(
      title: tr(lang, 'app.name'),
      debugShowCheckedModeBanner: false,
      theme: buildTheme(),
      home: const _Root(),
    );
  }
}

/// Decides what to show: sign-in, organization choice or the task list.
class _Root extends StatelessWidget {
  const _Root();

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    if (!state.ready) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (!state.signedIn) return const LoginScreen();
    if (state.needsOrganization) return const OrgScreen();
    return const HomeScreen();
  }
}
