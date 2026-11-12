import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import '../state/app_state.dart';
import '../theme.dart';
import 'widgets.dart';

class OrgScreen extends StatelessWidget {
  const OrgScreen({super.key, this.canGoBack = false});

  final bool canGoBack;

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final memberships = state.session?.memberships ?? [];
    return Scaffold(
      appBar: AppBar(
        leading: canGoBack ? const BackButton() : null,
        automaticallyImplyLeading: canGoBack,
        title: Text(context.t('org.title')),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            context.t('org.subtitle'),
            style: const TextStyle(color: Fx.muted),
          ),
          const SizedBox(height: 16),
          for (final m in memberships)
            FxCard(
              onTap: () async {
                await state.selectOrganization(m.organizationId);
                if (canGoBack && context.mounted) Navigator.of(context).pop();
              },
              borderColor: m.organizationId == state.session?.orgId
                  ? Fx.primary
                  : null,
              child: Row(
                children: [
                  const Icon(Icons.apartment, color: Fx.primary),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      m.organizationName,
                      style: const TextStyle(
                        fontSize: 17,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                  if (m.organizationId == state.session?.orgId)
                    const Icon(Icons.check_circle, color: Fx.primary),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
