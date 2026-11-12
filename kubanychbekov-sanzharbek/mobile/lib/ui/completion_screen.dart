import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import '../data/api_client.dart';
import '../models/models.dart';
import '../state/app_state.dart';
import '../theme.dart';
import 'widgets.dart';

/// Complete the work: final note (20+ characters) and at least one photo on the server.
/// This needs the server (MOB-08), so it is disabled while offline.
class CompletionScreen extends StatefulWidget {
  const CompletionScreen({super.key, required this.assignmentId});

  final int assignmentId;

  @override
  State<CompletionScreen> createState() => _CompletionScreenState();
}

class _CompletionScreenState extends State<CompletionScreen> {
  final _summary = TextEditingController();

  // One id for this completion attempt: a retry after a lost response is then harmless.
  final String _commandId = AppState.newCommandId();
  bool _busy = false;
  String? _error;
  int? _remotePhotos;

  @override
  void initState() {
    super.initState();
    _loadPhotos();
  }

  @override
  void dispose() {
    _summary.dispose();
    super.dispose();
  }

  Task? _task(AppState state) {
    final found = state.tasks.where(
      (t) => t.assignmentId == widget.assignmentId,
    );
    return found.isEmpty ? null : found.first;
  }

  Future<void> _loadPhotos() async {
    final state = context.read<AppState>();
    final task = _task(state);
    if (task == null) return;
    try {
      final photos = await state.loadAttachments(task.requestId);
      if (mounted) setState(() => _remotePhotos = photos.length);
    } on ApiException {
      // keep the previous number; the server still verifies on submit
    }
  }

  Future<void> _submit() async {
    final state = context.read<AppState>();
    final task = _task(state);
    if (task == null || _busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await state.complete(task, _summary.text, _commandId);
      if (!mounted) return;
      await Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => SuccessScreen(requestId: task.requestId),
        ),
      );
    } on ApiException catch (e) {
      setState(
        () => _error = e.isNetwork
            ? context.t('offline.onlineOnly')
            : context.err(e),
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final task = _task(state);
    final waiting = task == null
        ? 0
        : state
              .queueFor(task.requestId)
              .where((i) => i.type == QueueType.photo)
              .length;
    final long = _summary.text.trim().length >= 20;
    return Scaffold(
      appBar: AppBar(title: Text(context.t('complete.title'))),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const OfflineBanner(),
          TextField(
            controller: _summary,
            maxLines: 6,
            maxLength: 2000,
            onChanged: (_) => setState(() {}),
            decoration: fieldDecoration(
              context.t('complete.summary'),
              hint: context.t('complete.summaryHint'),
            ),
          ),
          const SizedBox(height: 10),
          FxCard(
            child: Row(
              children: [
                Icon(
                  (_remotePhotos ?? 0) > 0
                      ? Icons.check_circle
                      : Icons.photo_camera_outlined,
                  color: (_remotePhotos ?? 0) > 0 ? Fx.ok : Fx.warn,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    context.t('complete.photos', {
                      'n': _remotePhotos ?? '?',
                      'm': waiting,
                    }),
                  ),
                ),
              ],
            ),
          ),
          if (waiting > 0)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Text(
                context.t('complete.needSync'),
                style: const TextStyle(color: Fx.orange, fontSize: 13),
              ),
            ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Text(_error!, style: const TextStyle(color: Fx.danger)),
            ),
          PrimaryButton(
            label: context.t('complete.submit'),
            icon: Icons.task_alt,
            busy: _busy,
            onPressed: state.online && long ? _submit : null,
          ),
          if (!state.online)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(
                context.t('offline.onlineOnly'),
                style: const TextStyle(color: Fx.orange, fontSize: 12),
              ),
            ),
        ],
      ),
    );
  }
}

class SuccessScreen extends StatelessWidget {
  const SuccessScreen({super.key, required this.requestId});

  final int requestId;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(28),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 120,
                height: 120,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(color: Fx.ok, width: 4),
                ),
                child: const Icon(Icons.check, size: 64, color: Fx.ok),
              ),
              const SizedBox(height: 24),
              Text(
                context.t('complete.successTitle'),
                style: const TextStyle(
                  fontSize: 26,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 10),
              Text(
                context.t('complete.successText', {'id': requestId}),
                textAlign: TextAlign.center,
                style: const TextStyle(color: Fx.muted),
              ),
              const SizedBox(height: 32),
              PrimaryButton(
                label: context.t('complete.toTasks'),
                icon: Icons.assignment,
                onPressed: () =>
                    Navigator.of(context).popUntil((r) => r.isFirst),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
