import 'dart:io';

import '../models/models.dart';
import 'api_client.dart';
import 'local_store.dart';

class SyncResult {
  const SyncResult({
    this.sent = 0,
    this.conflicts = 0,
    this.failed = 0,
    this.offline = false,
    this.unauthorized = false,
  });

  final int sent;
  final int conflicts;
  final int failed;

  /// The connection dropped: the rest of the queue is untouched and will be tried again.
  final bool offline;

  /// The server rejected the token: nothing is lost, the user signs in again (AUTH-04).
  final bool unauthorized;

  bool get didAnything => sent + conflicts + failed > 0;
}

/// Delivers the offline queue in order with stable command ids (MOB-05, MOB-06).
///
/// Because every attempt carries the same `client_command_id`, a lost response is harmless:
/// the retry returns the original result and the server still holds exactly one note or file.
class SyncService {
  SyncService(this._store);

  final LocalStore _store;
  bool _running = false;

  bool get running => _running;

  Future<SyncResult> processQueue(ApiClient api) async {
    if (_running) return const SyncResult(); // never two rounds at once
    _running = true;
    var sent = 0, conflicts = 0, failed = 0;
    try {
      final items = await _store.loadQueue();
      for (final item in items) {
        if (item.state != QueueState.pending) continue; // failed/conflict wait for the user
        try {
          await _deliver(api, item);
          await _store.deleteQueueItem(item.id);
          await _removeFile(item);
          sent++;
        } on ApiException catch (e) {
          if (e.isNetwork) {
            await _store.putQueueItem(item.copyWith(attempts: item.attempts + 1));
            return SyncResult(sent: sent, conflicts: conflicts, failed: failed, offline: true);
          }
          if (e.isUnauthorized) {
            return SyncResult(
              sent: sent, conflicts: conflicts, failed: failed, unauthorized: true,
            );
          }
          if (e.isConflict || e.code == 'request_not_found') {
            await _store.putQueueItem(item.copyWith(
              state: QueueState.conflict,
              attempts: item.attempts + 1,
              error: e.message,
              conflictCode: e.code,
            ));
            conflicts++;
          } else {
            await _store.putQueueItem(item.copyWith(
              state: QueueState.failed,
              attempts: item.attempts + 1,
              error: e.message,
              conflictCode: e.code,
            ));
            failed++;
          }
        }
      }
      return SyncResult(sent: sent, conflicts: conflicts, failed: failed);
    } finally {
      _running = false;
    }
  }

  Future<void> _deliver(ApiClient api, QueueItem item) async {
    switch (item.type) {
      case QueueType.note:
        await api.post('requests/${item.requestId}/notes', body: {
          'body': item.body,
          'visibility': item.visibility,
          'client_command_id': item.id,
        });
      case QueueType.photo:
        await api.postFile(
          'requests/${item.requestId}/attachments',
          filePath: item.filePath!,
          fields: {'client_command_id': item.id, 'purpose': item.purpose},
        );
    }
  }

  Future<void> _removeFile(QueueItem item) async {
    final path = item.filePath;
    if (path == null) return;
    final file = File(path);
    if (await file.exists()) await file.delete();
  }
}
