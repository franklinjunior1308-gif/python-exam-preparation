import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import '../data/api_client.dart';
import '../state/app_state.dart';
import '../theme.dart';
import 'widgets.dart';

const _demoPassword =
    'Demo-2345!'; // demo-only account created by the seed command
const _demoAccounts = ['tech1.a@fixflow.test', 'tech2.a@fixflow.test'];

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _server = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _busy = false;
  bool _hidden = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    final state = context.read<AppState>();
    state.savedServerUrl().then((url) {
      if (mounted) _server.text = url;
    });
    if (state.session != null) _email.text = state.session!.email;
  }

  @override
  void dispose() {
    _server.dispose();
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_busy) return;
    final state = context.read<AppState>();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await state.login(_server.text, _email.text, _password.text);
    } on ApiException catch (e) {
      setState(
        () => _error = e.code == 'no_technician_role'
            ? context.t('login.noTechnicianRole')
            : context.err(e),
      );
    } on FormatException {
      setState(() => _error = context.t('err.network'));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final expired = state.session?.needsLogin ?? false;
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.bolt, color: Fx.primary, size: 40),
                      const SizedBox(width: 8),
                      const Text(
                        'FixFlow',
                        style: TextStyle(
                          fontSize: 30,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const Spacer(),
                      SegmentedButton<String>(
                        showSelectedIcon: false,
                        segments: const [
                          ButtonSegment(value: 'en', label: Text('EN')),
                          ButtonSegment(value: 'ru', label: Text('RU')),
                        ],
                        selected: {state.lang},
                        onSelectionChanged: (v) => state.setLang(v.first),
                      ),
                    ],
                  ),
                  const SizedBox(height: 28),
                  Text(
                    context.t('login.title'),
                    style: const TextStyle(
                      fontSize: 26,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    context.t('login.subtitle'),
                    style: const TextStyle(color: Fx.muted),
                  ),
                  const SizedBox(height: 20),
                  if (expired)
                    Container(
                      padding: const EdgeInsets.all(12),
                      margin: const EdgeInsets.only(bottom: 14),
                      decoration: BoxDecoration(
                        color: Fx.accent.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(context.t('login.expired')),
                    ),
                  TextField(
                    controller: _email,
                    keyboardType: TextInputType.emailAddress,
                    autofillHints: const [AutofillHints.username],
                    decoration: fieldDecoration(context.t('login.email')),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _password,
                    obscureText: _hidden,
                    autofillHints: const [AutofillHints.password],
                    onSubmitted: (_) => _submit(),
                    decoration: fieldDecoration(context.t('login.password'))
                        .copyWith(
                          suffixIcon: IconButton(
                            icon: Icon(
                              _hidden ? Icons.visibility : Icons.visibility_off,
                            ),
                            onPressed: () => setState(() => _hidden = !_hidden),
                          ),
                        ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _server,
                    keyboardType: TextInputType.url,
                    decoration: fieldDecoration(
                      context.t('login.server'),
                      hint: 'http://10.0.2.2:8000',
                    ),
                  ),
                  Padding(
                    padding: const EdgeInsets.only(top: 4, bottom: 12),
                    child: Text(
                      context.t('login.serverHint'),
                      style: const TextStyle(color: Fx.muted, fontSize: 12),
                    ),
                  ),
                  if (_error != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: Text(
                        _error!,
                        style: const TextStyle(color: Fx.danger),
                      ),
                    ),
                  PrimaryButton(
                    label: context.t('login.submit'),
                    onPressed: _submit,
                    busy: _busy,
                    icon: Icons.login,
                  ),
                  const SizedBox(height: 22),
                  Text(
                    context.t('login.demo'),
                    style: const TextStyle(color: Fx.muted, fontSize: 12),
                  ),
                  const SizedBox(height: 6),
                  for (final email in _demoAccounts)
                    TextButton(
                      onPressed: () => setState(() {
                        _email.text = email;
                        _password.text = _demoPassword;
                      }),
                      child: Align(
                        alignment: Alignment.centerLeft,
                        child: Text(email),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
