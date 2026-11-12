import 'package:image_picker/image_picker.dart';
import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import '../data/api_client.dart';
import '../i18n.dart';
import '../models/models.dart';
import '../state/app_state.dart';
import '../theme.dart';
import 'completion_screen.dart';
import 'materials_screen.dart';
import 'widgets.dart';

class TaskDetailScreen extends StatefulWidget {
  const TaskDetailScreen({super.key, required this.assignmentId});

  final int assignmentId;

  @override
  State<TaskDetailScreen> createState() => _TaskDetailScreenState();
}

class _TaskDetailScreenState extends State<TaskDetailScreen> {
  bool _busy = false;
  Future<List<RemoteNote>>? _notes;
  Future<List<RemoteAttachment>>? _photos;
  int? _loadedFor;
  int? _estimate;

  void _reloadRemote(Task task) {
    final state = context.read<AppState>();
    _loadedFor = task.requestId;
    _notes = state.loadNotes(task.requestId);
    _photos = state.loadAttachments(task.requestId);
    state
        .approvedEstimateCents(task.requestId)
        .then((value) {
          if (mounted) setState(() => _estimate = value);
        })
        .catchError((Object _) {
          // The estimate card is optional; offline or a refusal simply hides it.
        });
  }

  Future<void> _run(Future<void> Function() action) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      await action();
    } on ApiException catch (e) {
      if (mounted) {
        showMessage(
          context,
          e.isNetwork ? context.t('offline.onlineOnly') : context.err(e),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<String?> _askReason({
    required bool required,
    required String title,
    String? text,
  }) {
    final controller = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (ctx) {
        String? error;
        return StatefulBuilder(
          builder: (ctx, setInner) => AlertDialog(
            title: Text(title),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (text != null)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Text(text),
                  ),
                TextField(
                  controller: controller,
                  maxLines: 3,
                  decoration: fieldDecoration(
                    context.t('action.reason'),
                    errorText: error,
                  ),
                ),
              ],
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: Text(context.t('common.cancel')),
              ),
              TextButton(
                onPressed: () {
                  if (required && controller.text.trim().isEmpty) {
                    setInner(() => error = context.t('action.reasonRequired'));
                    return;
                  }
                  Navigator.pop(ctx, controller.text.trim());
                },
                child: Text(context.t('common.confirm')),
              ),
            ],
          ),
        );
      },
    );
  }

  Future<void> _addNote(Task task) async {
    final controller = TextEditingController();
    var internal = false;
    final result = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Fx.bg2,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setInner) => Padding(
          padding: EdgeInsets.fromLTRB(
            16,
            16,
            16,
            MediaQuery.of(ctx).viewInsets.bottom + 16,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                context.t('note.title'),
                style: const TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: controller,
                maxLines: 6,
                maxLength: 2000,
                decoration: fieldDecoration(context.t('note.hint')),
              ),
              SwitchListTile(
                value: internal,
                onChanged: (v) => setInner(() => internal = v),
                title: Text(
                  context.t('note.internal'),
                  style: const TextStyle(fontSize: 14),
                ),
                contentPadding: EdgeInsets.zero,
              ),
              PrimaryButton(
                label: context.t('common.save'),
                icon: Icons.save,
                onPressed: () {
                  if (controller.text.trim().isNotEmpty) {
                    Navigator.pop(ctx, true);
                  }
                },
              ),
            ],
          ),
        ),
      ),
    );
    if (result == true && mounted) {
      await context.read<AppState>().enqueueNote(
        task.requestId,
        controller.text,
        internal: internal,
      );
      if (mounted) showMessage(context, context.t('note.saved'));
    }
  }

  Future<void> _addPhoto(Task task) async {
    var purpose = 'after';
    ImageSource? source;
    await showModalBottomSheet<void>(
      context: context,
      backgroundColor: Fx.bg2,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setInner) => Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                context.t('photo.title'),
                style: const TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 12),
              SegmentedButton<String>(
                segments: [
                  ButtonSegment(
                    value: 'before',
                    label: Text(context.t('photo.before')),
                  ),
                  ButtonSegment(
                    value: 'after',
                    label: Text(context.t('photo.after')),
                  ),
                ],
                selected: {purpose},
                onSelectionChanged: (v) => setInner(() => purpose = v.first),
              ),
              const SizedBox(height: 12),
              ListTile(
                leading: const Icon(Icons.photo_camera, color: Fx.primary),
                title: Text(context.t('photo.camera')),
                onTap: () {
                  source = ImageSource.camera;
                  Navigator.pop(ctx);
                },
              ),
              ListTile(
                leading: const Icon(Icons.photo_library, color: Fx.primary),
                title: Text(context.t('photo.gallery')),
                onTap: () {
                  source = ImageSource.gallery;
                  Navigator.pop(ctx);
                },
              ),
            ],
          ),
        ),
      ),
    );
    if (source == null || !mounted) return;
    final picked = await ImagePicker().pickImage(
      source: source!,
      maxWidth: 2000,
      imageQuality: 85,
    );
    if (picked == null || !mounted) return;
    await context.read<AppState>().enqueuePhoto(
      task.requestId,
      picked.path,
      purpose: purpose,
    );
    if (mounted) showMessage(context, context.t('photo.saved'));
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final matches = state.tasks.where(
      (t) => t.assignmentId == widget.assignmentId,
    );
    if (matches.isEmpty) {
      return Scaffold(
        appBar: AppBar(),
        body: EmptyState(context.t('err.assignment_changed')),
      );
    }
    final task = matches.first;
    if (_loadedFor != task.requestId && state.online) _reloadRemote(task);

    final tz = task.timezone;
    final online = state.online;
    final status = task.assignmentStatus;
    final can = task.allowedActions;
    final queued = state.queueFor(task.requestId);

    final actions = <Widget>[];
    if (status == 'SCHEDULED' && can.contains('ACCEPTED')) {
      actions.add(
        PrimaryButton(
          label: context.t('action.accept'),
          icon: Icons.check,
          busy: _busy,
          onPressed: online
              ? () => _run(() => state.transition(task, 'ACCEPTED'))
              : null,
        ),
      );
    }
    if (status == 'ACCEPTED' && can.contains('IN_PROGRESS')) {
      actions.add(
        PrimaryButton(
          label: context.t('action.start'),
          icon: Icons.play_arrow,
          busy: _busy,
          onPressed: online
              ? () => _run(() => state.transition(task, 'IN_PROGRESS'))
              : null,
        ),
      );
    }
    if (status == 'BLOCKED' && can.contains('IN_PROGRESS')) {
      actions.add(
        PrimaryButton(
          label: context.t('action.resume'),
          icon: Icons.play_arrow,
          busy: _busy,
          onPressed: online
              ? () async {
                  final reason = await _askReason(
                    required: true,
                    title: context.t('action.resume'),
                  );
                  if (reason != null) {
                    await _run(
                      () =>
                          state.transition(task, 'IN_PROGRESS', reason: reason),
                    );
                  }
                }
              : null,
        ),
      );
    }
    if (status == 'IN_PROGRESS') {
      actions.add(
        PrimaryButton(
          label: context.t('action.complete'),
          icon: Icons.task_alt,
          onPressed: online
              ? () => Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) =>
                        CompletionScreen(assignmentId: task.assignmentId),
                  ),
                )
              : null,
        ),
      );
      if (can.contains('BLOCKED')) {
        actions.add(const SizedBox(height: 8));
        actions.add(
          OutlinedButton.icon(
            onPressed: online && !_busy
                ? () async {
                    final reason = await _askReason(
                      required: true,
                      title: context.t('action.block'),
                    );
                    if (reason != null) {
                      await _run(
                        () => state.transition(task, 'BLOCKED', reason: reason),
                      );
                    }
                  }
                : null,
            icon: const Icon(Icons.block),
            label: Text(context.t('action.block')),
          ),
        );
      }
    }
    if (status == 'SCHEDULED' || status == 'ACCEPTED') {
      actions.add(const SizedBox(height: 8));
      actions.add(
        OutlinedButton.icon(
          style: OutlinedButton.styleFrom(foregroundColor: Fx.danger),
          onPressed: online && !_busy
              ? () async {
                  final reason = await _askReason(
                    required: false,
                    title: context.t('action.declineTitle'),
                    text: context.t('action.declineText'),
                  );
                  if (reason != null) {
                    await _run(() async {
                      await state.decline(
                        task,
                        reason: reason.isEmpty ? null : reason,
                      );
                      if (context.mounted) Navigator.of(context).pop();
                    });
                  }
                }
              : null,
          icon: const Icon(Icons.cancel_outlined),
          label: Text(context.t('action.decline')),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(context.t('detail.title', {'id': task.requestId})),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 12),
            child: Pill(
              context.t('status.$status'),
              color: Fx.statusColor(status),
            ),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const OfflineBanner(),
          Text(
            task.title,
            style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 6),
          Wrap(
            spacing: 8,
            children: [
              Pill(
                context.t('priority.${task.priority}'),
                color: Fx.priorityColor(task.priority),
              ),
              Pill(task.categoryName, color: Fx.accent),
            ],
          ),
          const SizedBox(height: 16),
          FxCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _info(
                  Icons.place_outlined,
                  context.t('detail.property'),
                  '${task.propertyName}\n${task.propertyAddress}',
                ),
                _info(
                  Icons.schedule,
                  context.t('detail.visit'),
                  formatRange(task.startAt, task.endAt, tz, state.lang),
                ),
                _info(
                  Icons.person_outline,
                  context.t('detail.customer'),
                  task.customerName,
                ),
                if (task.assetLabel != null)
                  _info(
                    Icons.precision_manufacturing_outlined,
                    context.t('detail.equipment'),
                    task.assetLabel!,
                  ),
                if (task.contactInstructions != null &&
                    task.contactInstructions!.isNotEmpty)
                  _info(
                    Icons.call_outlined,
                    context.t('detail.contact'),
                    task.contactInstructions!,
                  ),
              ],
            ),
          ),
          FxCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  context.t('detail.description'),
                  style: const TextStyle(color: Fx.muted, fontSize: 12),
                ),
                const SizedBox(height: 4),
                Text(task.description),
              ],
            ),
          ),
          if (actions.isNotEmpty) ...[
            Text(
              context.t('detail.actions'),
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            ...actions,
            if (!online)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(
                  context.t('offline.onlineOnly'),
                  style: const TextStyle(color: Fx.orange, fontSize: 12),
                ),
              ),
            const SizedBox(height: 16),
          ],
          if (task.isActive) ...[
            Text(
              context.t('detail.work'),
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => _addNote(task),
                    icon: const Icon(Icons.edit_note),
                    label: Text(context.t('action.addNote')),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => _addPhoto(task),
                    icon: const Icon(Icons.add_a_photo_outlined),
                    label: Text(context.t('action.addPhoto')),
                  ),
                ),
              ],
            ),
            if (status == 'IN_PROGRESS') ...[
              const SizedBox(height: 10),
              OutlinedButton.icon(
                onPressed: online
                    ? () => Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) =>
                              MaterialsScreen(assignmentId: task.assignmentId),
                        ),
                      )
                    : null,
                icon: const Icon(Icons.inventory_2_outlined),
                label: Text(context.t('action.materials')),
              ),
            ],
            const SizedBox(height: 12),
          ],
          if (_estimate != null)
            FxCard(
              child: Row(
                children: [
                  const Icon(Icons.request_quote_outlined, color: Fx.primary),
                  const SizedBox(width: 12),
                  Expanded(child: Text(context.t('detail.estimate'))),
                  Text(
                    formatKgs(_estimate!),
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                ],
              ),
            ),
          if (queued.isNotEmpty) ...[
            Text(
              context.t('detail.waiting'),
              style: const TextStyle(
                color: Fx.warn,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 6),
            for (final item in queued)
              ListTile(
                dense: true,
                contentPadding: EdgeInsets.zero,
                leading: Icon(
                  item.type == QueueType.note
                      ? Icons.notes
                      : Icons.image_outlined,
                  color: Fx.warn,
                ),
                title: Text(
                  item.type == QueueType.note
                      ? (item.body ?? '')
                      : context.t('queue.photo'),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                trailing: Pill(
                  item.state == QueueState.pending
                      ? context.t('queue.pending')
                      : item.state == QueueState.conflict
                      ? context.t('queue.conflict')
                      : context.t('queue.failed'),
                  color: item.state == QueueState.pending ? Fx.warn : Fx.orange,
                ),
              ),
            const SizedBox(height: 8),
          ],
          Text(
            context.t('detail.notes'),
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 6),
          FutureBuilder<List<RemoteNote>>(
            future: _notes,
            builder: (context, snap) {
              final notes = snap.data ?? const <RemoteNote>[];
              if (notes.isEmpty) {
                return Text(
                  context.t('detail.noNotes'),
                  style: const TextStyle(color: Fx.muted),
                );
              }
              return Column(
                children: [
                  for (final n in notes)
                    FxCard(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '${n.author} · ${formatWhen(n.createdAt, tz, state.lang)}'
                            '${n.visibility == 'internal' ? ' · internal' : ''}',
                            style: const TextStyle(
                              color: Fx.muted,
                              fontSize: 12,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(n.body),
                        ],
                      ),
                    ),
                ],
              );
            },
          ),
          const SizedBox(height: 8),
          Text(
            context.t('detail.photos'),
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 6),
          FutureBuilder<List<RemoteAttachment>>(
            future: _photos,
            builder: (context, snap) {
              final photos = snap.data ?? const <RemoteAttachment>[];
              final api = state.api;
              if (photos.isEmpty || api == null) {
                return Text(
                  context.t('detail.noPhotos'),
                  style: const TextStyle(color: Fx.muted),
                );
              }
              return Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final p in photos)
                    ClipRRect(
                      borderRadius: BorderRadius.circular(10),
                      child: Image.network(
                        api.fileUri(p.id).toString(),
                        headers: api.imageHeaders,
                        width: 100,
                        height: 100,
                        fit: BoxFit.cover,
                        errorBuilder: (_, _, _) => Container(
                          width: 100,
                          height: 100,
                          color: Fx.surface2,
                          child: const Icon(Icons.broken_image),
                        ),
                      ),
                    ),
                ],
              );
            },
          ),
          const SizedBox(height: 24),
        ],
      ),
    );
  }

  Widget _info(IconData icon, String label, String value) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 6),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 20, color: Fx.primary),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: const TextStyle(color: Fx.muted, fontSize: 12),
              ),
              Text(value),
            ],
          ),
        ),
      ],
    ),
  );
}
