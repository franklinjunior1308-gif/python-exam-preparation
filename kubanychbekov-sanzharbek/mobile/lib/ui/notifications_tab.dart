import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import '../data/api_client.dart';
import '../i18n.dart';
import '../state/app_state.dart';
import '../theme.dart';
import 'task_detail_screen.dart';
import 'widgets.dart';

class NotificationsTab extends StatelessWidget {
  const NotificationsTab({super.key});

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final tz = state.membership?.timezone ?? 'Asia/Bishkek';
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
          child: Row(
            children: [
              Expanded(
                child: Text(
                  context.t('notif.title'),
                  style: const TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              if (state.unreadNotifications > 0)
                TextButton(
                  onPressed: () async {
                    try {
                      await state.markAllRead();
                    } on ApiException catch (e) {
                      if (context.mounted) showMessage(context, context.err(e));
                    }
                  },
                  child: Text(context.t('notif.markRead')),
                ),
            ],
          ),
        ),
        const OfflineBanner(),
        Expanded(
          child: RefreshIndicator(
            onRefresh: state.loadNotifications,
            child: state.notifications.isEmpty
                ? ListView(
                    children: [
                      EmptyState(
                        context.t('notif.empty'),
                        icon: Icons.notifications_none,
                      ),
                    ],
                  )
                : ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      for (final n in state.notifications)
                        FxCard(
                          borderColor: n.unread ? Fx.primary : null,
                          onTap: () {
                            final task = state.tasks.where(
                              (t) => t.requestId == n.requestId,
                            );
                            if (task.isNotEmpty) {
                              Navigator.of(context).push(
                                MaterialPageRoute(
                                  builder: (_) => TaskDetailScreen(
                                    assignmentId: task.first.assignmentId,
                                  ),
                                ),
                              );
                            }
                          },
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Icon(
                                n.unread
                                    ? Icons.notifications_active
                                    : Icons.notifications_none,
                                color: n.unread ? Fx.primary : Fx.muted,
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      trNotificationTitle(
                                        state.lang,
                                        n.type,
                                        n.requestId,
                                        n.title,
                                      ),
                                      style: const TextStyle(
                                        fontWeight: FontWeight.w700,
                                      ),
                                    ),
                                    if (n.body.isNotEmpty)
                                      Text(
                                        n.body,
                                        style: const TextStyle(
                                          color: Fx.muted,
                                          fontSize: 13,
                                        ),
                                      ),
                                    const SizedBox(height: 4),
                                    Text(
                                      formatWhen(n.createdAt, tz, state.lang),
                                      style: const TextStyle(
                                        color: Fx.muted,
                                        fontSize: 11,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        ),
                    ],
                  ),
          ),
        ),
      ],
    );
  }
}
