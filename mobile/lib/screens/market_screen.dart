import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';

class MarketScreen extends StatefulWidget {
  const MarketScreen({super.key});

  @override
  State<MarketScreen> createState() => _MarketScreenState();
}

class _MarketScreenState extends State<MarketScreen> {
  String _commodity = 'Maize';
  Map<String, dynamic>? _summary;
  bool _loading = false;
  String? _error;

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = context.read<ApiService>();
      final data = await api.marketSummary(_commodity);
      setState(() => _summary = data);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('🏪 Market Intelligence')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(
            decoration: const InputDecoration(
              labelText: 'Commodity',
              border: OutlineInputBorder(),
              hintText: 'e.g. Maize, Beans',
            ),
            onChanged: (v) => _commodity = v.trim().isEmpty ? 'Maize' : v.trim(),
            onSubmitted: (_) => _load(),
          ),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: _loading ? null : _load,
            child: Text(_loading ? 'Loading…' : 'Load Summary'),
          ),
          const SizedBox(height: 16),
          if (_error != null)
            Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          if (_summary != null) ...[
            _tile('Best market', '${_summary!['best_market'] ?? '—'}'),
            _tile('Best price', '${_summary!['best_price'] ?? '—'} UGX'),
            _tile('Worst market', '${_summary!['worst_market'] ?? '—'}'),
            _tile('Worst price', '${_summary!['worst_price'] ?? '—'} UGX'),
            _tile('National avg', '${_summary!['national_avg'] ?? '—'} UGX'),
          ],
        ],
      ),
    );
  }

  Widget _tile(String label, String value) {
    return Card(
      child: ListTile(
        title: Text(label),
        trailing: Text(value, style: const TextStyle(fontWeight: FontWeight.w600)),
      ),
    );
  }
}
