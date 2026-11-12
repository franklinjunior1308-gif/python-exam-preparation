import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import '../data/api_client.dart';
import '../i18n.dart';
import '../models/models.dart';
import '../state/app_state.dart';
import '../theme.dart';
import 'widgets.dart';

/// Parses "1,5" or "1.5"; returns null unless it is a positive number with at most 3 decimals.
String? parseQuantity(String raw) {
  final text = raw.trim().replaceAll(',', '.');
  if (!RegExp(r'^\d{1,9}(\.\d{1,3})?$').hasMatch(text)) return null;
  return double.parse(text) > 0 ? text : null;
}

/// Write materials off a request while the work is in progress. Needs the server (MOB-08):
/// the stock check and the write-off happen in one database transaction on the backend.
class MaterialsScreen extends StatefulWidget {
  const MaterialsScreen({super.key, required this.assignmentId});

  final int assignmentId;

  @override
  State<MaterialsScreen> createState() => _MaterialsScreenState();
}

class _MaterialsScreenState extends State<MaterialsScreen> {
  final _search = TextEditingController();
  List<InventoryItem>? _items;
  List<MaterialUse> _usages = [];
  String? _error;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Task? _task(AppState state) {
    final found = state.tasks.where(
      (t) => t.assignmentId == widget.assignmentId,
    );
    return found.isEmpty ? null : found.first;
  }

  Future<void> _load() async {
    final state = context.read<AppState>();
    final task = _task(state);
    if (task == null) return;
    try {
      final items = await state.loadInventory();
      final usages = await state.loadUsages(task.requestId);
      if (!mounted) return;
      setState(() {
        _items = items;
        _usages = usages;
        _error = null;
      });
    } on ApiException catch (e) {
      if (mounted) {
        setState(
          () => _error = e.isNetwork
              ? context.t('offline.onlineOnly')
              : context.err(e),
        );
      }
    }
  }

  Future<void> _writeOff(InventoryItem item) async {
    final state = context.read<AppState>();
    final task = _task(state);
    if (task == null) return;
    final controller = TextEditingController(text: '1');
    final commandId = AppState.newCommandId(); // one id per dialog: pressing twice cannot double-write
    String? error;
    final quantity = await showDialog<String>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setInner) => AlertDialog(
          title: Text(item.name),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                context.t('materials.stock', {
                  'n': item.stock,
                  'unit': item.unit,
                }),
                style: const TextStyle(color: Fx.muted),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: controller,
                autofocus: true,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: fieldDecoration(
                  context.t('materials.quantity', {'unit': item.unit}),
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
                final parsed = parseQuantity(controller.text);
                if (parsed == null) {
                  setInner(() => error = context.t('materials.badQuantity'));
                  return;
                }
                Navigator.pop(ctx, parsed);
              },
              child: Text(context.t('materials.writeOff')),
            ),
          ],
        ),
      ),
    );
    if (quantity == null || !mounted) return;
    setState(() => _busy = true);
    try {
      await state.useMaterial(task, item.id, quantity, commandId);
      if (mounted) showMessage(context, context.t('materials.done'));
      await _load();
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

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final tz = state.membership?.timezone ?? 'Asia/Bishkek';
    final query = _search.text.trim().toLowerCase();
    final items = (_items ?? [])
        .where(
          (i) =>
              query.isEmpty ||
              i.name.toLowerCase().contains(query) ||
              i.code.toLowerCase().contains(query),
        )
        .toList();
    return Scaffold(
      appBar: AppBar(title: Text(context.t('materials.title'))),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const OfflineBanner(),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Text(_error!, style: const TextStyle(color: Fx.danger)),
            ),
          TextField(
            controller: _search,
            onChanged: (_) => setState(() {}),
            decoration: fieldDecoration(context.t('materials.search'))
                .copyWith(prefixIcon: const Icon(Icons.search)),
          ),
          const SizedBox(height: 12),
          if (_items == null && _error == null)
            const Center(child: CircularProgressIndicator()),
          if (_items != null && items.isEmpty)
            EmptyState(context.t('materials.noMatches')),
          for (final item in items)
            FxCard(
              onTap: state.online && !_busy ? () => _writeOff(item) : null,
              child: Row(
                children: [
                  const Icon(Icons.inventory_2_outlined, color: Fx.primary),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          item.name,
                          style: const TextStyle(fontWeight: FontWeight.w700),
                        ),
                        Text(
                          '${item.code} · ${context.t('materials.stock', {'n': item.stock, 'unit': item.unit})}'
                          '${item.lowStock ? ' · ${context.t('materials.low')}' : ''}',
                          style: TextStyle(
                            color: item.lowStock ? Fx.orange : Fx.muted,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Text(
                    formatKgs(item.unitPriceCents),
                    style: const TextStyle(color: Fx.muted, fontSize: 12),
                  ),
                ],
              ),
            ),
          const SizedBox(height: 16),
          Text(
            context.t('materials.used'),
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 6),
          if (_usages.isEmpty)
            Text(
              context.t('materials.none'),
              style: const TextStyle(color: Fx.muted),
            )
          else
            for (final use in _usages)
              ListTile(
                dense: true,
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.check_circle_outline, color: Fx.ok),
                title: Text('${use.itemName} × ${use.quantity}'),
                subtitle: Text(formatWhen(use.createdAt, tz, state.lang)),
                trailing: Text(formatKgs(use.totalCents)),
              ),
        ],
      ),
    );
  }
}
