import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import '../i18n.dart';
import '../models/models.dart';
import '../state/app_state.dart';
import '../theme.dart';
import 'notifications_tab.dart';
import 'profile_tab.dart';
import 'queue_tab.dart';
import 'task_detail_screen.dart';
import 'widgets.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();

    // one-shot messages from background sync
    final notice = state.notice;
    if (notice != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        final parts = notice.split(':');
        final n = parts.length > 1 ? parts[1] : '';
        if (parts[0] == 'synced') {
          showMessage(context, context.t('queue.synced', {'n': n}));
        }
        if (parts[0] == 'conflicts') {
          showMessage(context, context.t('queue.conflicts', {'n': n}));
        }
        state.clearNotice();
      });
    }

    final pages = <Widget>[
      const TasksTab(),
      const QueueTab(),
      const NotificationsTab(),
      const ProfileTab(),
    ];
    return Scaffold(
      body: SafeArea(
        child: IndexedStack(index: _index, children: pages),
      ),
      bottomNavigationBar: NavigationBar(
        backgroundColor: Fx.bg2,
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: [
          NavigationDestination(
            icon: const Icon(Icons.assignment_outlined),
            selectedIcon: const Icon(Icons.assignment),
            label: context.t('tabs.tasks'),
          ),
          NavigationDestination(
            icon: Badge(
              isLabelVisible: state.queue.isNotEmpty,
              label: Text('${state.queue.length}'),
              child: const Icon(Icons.sync_outlined),
            ),
            selectedIcon: const Icon(Icons.sync),
            label: context.t('tabs.queue'),
          ),
          NavigationDestination(
            icon: Badge(
              isLabelVisible: state.unreadNotifications > 0,
              label: Text('${state.unreadNotifications}'),
              child: const Icon(Icons.notifications_outlined),
            ),
            selectedIcon: const Icon(Icons.notifications),
            label: context.t('tabs.notifications'),
          ),
          NavigationDestination(
            icon: const Icon(Icons.person_outline),
            selectedIcon: const Icon(Icons.person),
            label: context.t('tabs.profile'),
          ),
        ],
      ),
    );
  }
}

class TasksTab extends StatelessWidget {
  const TasksTab({super.key});

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final tz = state.membership?.timezone ?? 'Asia/Bishkek';
    final today = localDay(DateTime.now().toUtc(), tz);

    final active = state.tasks.where((t) => t.isActive).toList();
    final todays = state.tasks
        .where((t) => t.isActive && localDay(t.startAt, tz) == today)
        .toList();
    final done = state.tasks.where((t) => t.isDone).toList().reversed.toList();

    return DefaultTabController(
      length: 3,
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        context.t('tasks.title'),
                        style: const TextStyle(
                          fontSize: 24,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      Text(
                        state.lastSync == null
                            ? context.t('tasks.neverSynced')
                            : context.t('tasks.lastSync', {
                                'time': formatWhen(
                                  state.lastSync!,
                                  tz,
                                  state.lang,
                                ),
                              }),
                        style: const TextStyle(color: Fx.muted, fontSize: 12),
                      ),
                    ],
                  ),
                ),
                if (state.waitingCount > 0)
                  TextButton.icon(
                    onPressed: state.syncing ? null : () => state.runSync(),
                    icon: const Icon(Icons.sync, size: 18),
                    label: Text(
                      context.t('offline.sync', {'n': state.waitingCount}),
                    ),
                  ),
              ],
            ),
          ),
          const OfflineBanner(),
          TabBar(
            tabs: [
              Tab(text: '${context.t('tasks.active')} (${active.length})'),
              Tab(text: '${context.t('tasks.today')} (${todays.length})'),
              Tab(text: context.t('tasks.done')),
            ],
          ),
          Expanded(
            child: TabBarView(
              children: [
                _TaskList(tasks: active),
                _TaskList(tasks: todays),
                _TaskList(tasks: done),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _TaskList extends StatelessWidget {
  const _TaskList({required this.tasks});

  final List<Task> tasks;

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    return RefreshIndicator(
      onRefresh: state.refresh,
      child: tasks.isEmpty
          ? ListView(children: [EmptyState(context.t('tasks.empty'))])
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [for (final task in tasks) TaskCard(task: task)],
            ),
    );
  }
}

class TaskCard extends StatelessWidget {
  const TaskCard({super.key, required this.task});

  final Task task;

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final tz = task.timezone;
    final pending = state.queueFor(task.requestId).length;
    return FxCard(
      onTap: () => Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => TaskDetailScreen(assignmentId: task.assignmentId),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                '#${task.requestId}',
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(width: 8),
              Pill(
                context.t('priority.${task.priority}'),
                color: Fx.priorityColor(task.priority),
              ),
              // the status shrinks instead of overflowing on narrow phones / long translations
              Expanded(
                child: Align(
                  alignment: Alignment.centerRight,
                  child: FittedBox(
                    fit: BoxFit.scaleDown,
                    child: Pill(
                      context.t('status.${task.assignmentStatus}'),
                      color: Fx.statusColor(task.assignmentStatus),
                    ),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            task.title,
            style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 6),
          Row(
            children: [
              const Icon(Icons.place_outlined, size: 16, color: Fx.muted),
              const SizedBox(width: 4),
              Expanded(
                child: Text(
                  '${task.propertyName}, ${task.propertyAddress}',
                  style: const TextStyle(color: Fx.muted, fontSize: 13),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Row(
            children: [
              const Icon(Icons.schedule, size: 16, color: Fx.muted),
              const SizedBox(width: 4),
              Expanded(
                child: Text(
                  formatRange(task.startAt, task.endAt, tz, state.lang),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: Fx.muted, fontSize: 13),
                ),
              ),
              if (pending > 0)
                Row(
                  children: [
                    const Icon(
                      Icons.cloud_upload_outlined,
                      size: 16,
                      color: Fx.warn,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      '$pending',
                      style: const TextStyle(color: Fx.warn, fontSize: 13),
                    ),
                  ],
                ),
            ],
          ),
        ],
      ),
    );
  }
}
