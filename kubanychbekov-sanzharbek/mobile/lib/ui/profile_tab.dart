import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import '../state/app_state.dart';
import '../theme.dart';
import 'org_screen.dart';
import 'widgets.dart';

class ProfileTab extends StatelessWidget {
  const ProfileTab({super.key});

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final session = state.session;
    final membership = state.membership;
    if (session == null) return const SizedBox.shrink();

    Widget row(String label, String value) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 120,
            child: Text(label, style: const TextStyle(color: Fx.muted)),
          ),
          Expanded(child: Text(value)),
        ],
      ),
    );

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(
          context.t('profile.title'),
          style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 16),
        FxCard(
          child: Column(
            children: [
              Row(
                children: [
                  CircleAvatar(
                    radius: 28,
                    backgroundColor: Fx.surface2,
                    child: Text(
                      session.userName.isEmpty
                          ? '?'
                          : session.userName[0].toUpperCase(),
                      style: const TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          session.userName,
                          style: const TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        Text(
                          session.email,
                          style: const TextStyle(color: Fx.muted),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const Divider(height: 24),
              row(
                context.t('profile.org'),
                membership?.organizationName ?? '-',
              ),
              row(context.t('profile.role'), context.t('profile.technician')),
              row(context.t('profile.server'), session.serverUrl),
            ],
          ),
        ),
        if (session.memberships.length > 1)
          OutlinedButton.icon(
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(
                builder: (_) => const OrgScreen(canGoBack: true),
              ),
            ),
            icon: const Icon(Icons.swap_horiz),
            label: Text(context.t('profile.switchOrg')),
          ),
        const SizedBox(height: 16),
        Text(
          context.t('profile.language'),
          style: const TextStyle(color: Fx.muted),
        ),
        const SizedBox(height: 6),
        SegmentedButton<String>(
          segments: const [
            ButtonSegment(value: 'en', label: Text('English')),
            ButtonSegment(value: 'ru', label: Text('Русский')),
          ],
          selected: {state.lang},
          onSelectionChanged: (v) => state.setLang(v.first),
        ),
        const SizedBox(height: 28),
        OutlinedButton.icon(
          style: OutlinedButton.styleFrom(foregroundColor: Fx.danger),
          onPressed: () => _signOut(context, state),
          icon: const Icon(Icons.logout),
          label: Text(context.t('profile.signOut')),
        ),
      ],
    );
  }

  Future<void> _signOut(BuildContext context, AppState state) async {
    if (state.queue.isNotEmpty) {
      final ok = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text(context.t('profile.signOut')),
          content: Text(
            context.t('profile.signOutWarn', {'n': state.queue.length}),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: Text(context.t('common.cancel')),
            ),
            TextButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: Text(context.t('common.confirm')),
            ),
          ],
        ),
      );
      if (ok != true) return;
    }
    await state.logout();
  }
}
