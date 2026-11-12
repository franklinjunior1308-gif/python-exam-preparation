import 'dart:io';

import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import '../i18n.dart';
import '../models/models.dart';
import '../state/app_state.dart';
import '../theme.dart';
import 'widgets.dart';

/// Everything saved on the phone that has not reached the server yet (MOB-05).
class QueueTab extends StatelessWidget {
  const QueueTab({super.key});

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final tz = state.membership?.timezone ?? 'Asia/Bishkek';
    return Column(children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
        child: Row(children: [
          Expanded(
            child: Text(context.t('queue.title'),
                style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w800)),
          ),
          FilledButton.icon(
            onPressed: state.syncing || state.waitingCount == 0 ? null : () => state.runSync(),
            icon: state.syncing
                ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.sync),
            label: Text(context.t('queue.syncNow')),
          ),
        ]),
      ),
      const OfflineBanner(),
      Expanded(
        child: state.queue.isEmpty
            ? EmptyState(context.t('queue.empty'), icon: Icons.cloud_done_outlined)
            : ListView(padding: const EdgeInsets.all(16), children: [
                for (final item in state.queue) QueueCard(item: item, timezone: tz),
              ]),
      ),
    ]);
  }
}

class QueueCard extends StatelessWidget {
  const QueueCard({super.key, required this.item, required this.timezone});

  final QueueItem item;
  final String timezone;

  Color get _color => switch (item.state) {
        QueueState.pending => Fx.warn,
        QueueState.failed => Fx.danger,
        QueueState.conflict => Fx.orange,
      };

  @override
  Widget build(BuildContext context) {
    final state = context.read<AppState>();
    final lang = context.watch<AppState>().lang;
    final label = switch (item.state) {
      QueueState.pending => context.t('queue.pending'),
      QueueState.failed => context.t('queue.failed'),
      QueueState.conflict => context.t('queue.conflict'),
    };
    return FxCard(
      borderColor: item.state == QueueState.pending ? null : _color,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(item.type == QueueType.note ? Icons.sticky_note_2_outlined : Icons.photo_outlined,
              color: Fx.primary),
          const SizedBox(width: 8),
          Text('${item.type == QueueType.note ? context.t('queue.note') : context.t('queue.photo')}'
              ' · #${item.requestId}',
              style: const TextStyle(fontWeight: FontWeight.w700)),
          const Spacer(),
          Pill(label, color: _color),
        ]),
        const SizedBox(height: 8),
        if (item.type == QueueType.note)
          Text(item.body ?? '', maxLines: 4, overflow: TextOverflow.ellipsis)
        else if (item.filePath != null && File(item.filePath!).existsSync())
          ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: Image.file(File(item.filePath!), height: 120, fit: BoxFit.cover),
          ),
        const SizedBox(height: 6),
        Text(context.t('queue.queuedAt', {'time': formatWhen(item.createdAt, timezone, lang)}),
            style: const TextStyle(color: Fx.muted, fontSize: 12)),
        if (item.state == QueueState.conflict)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text('${context.t('queue.conflictHelp')}\n${item.error ?? ''}',
                style: const TextStyle(color: Fx.orange, fontSize: 13)),
          ),
        if (item.state == QueueState.failed && item.error != null)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text(item.error!, style: const TextStyle(color: Fx.danger, fontSize: 13)),
          ),
        const SizedBox(height: 8),
        Row(mainAxisAlignment: MainAxisAlignment.end, children: [
          TextButton.icon(
            onPressed: () => state.retryItem(item.id),
            icon: const Icon(Icons.refresh, size: 18),
            label: Text(context.t('common.retry')),
          ),
          TextButton.icon(
            onPressed: () => _confirmDelete(context, state),
            icon: const Icon(Icons.delete_outline, size: 18, color: Fx.danger),
            label: Text(context.t('common.delete'), style: const TextStyle(color: Fx.danger)),
          ),
        ]),
      ]),
    );
  }

  Future<void> _confirmDelete(BuildContext context, AppState state) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(context.t('queue.deleteTitle')),
        content: Text(context.t('queue.deleteText')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text(context.t('common.cancel'))),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: Text(context.t('common.delete'), style: const TextStyle(color: Fx.danger)),
          ),
        ],
      ),
    );
    if (ok == true) await state.discardItem(item.id);
  }
}
