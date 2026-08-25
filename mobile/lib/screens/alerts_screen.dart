import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../widgets/data_source_chip.dart';

class AlertsScreen extends StatefulWidget {
  const AlertsScreen({super.key});

  @override
  State<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends State<AlertsScreen> {
  final _watchlist = <String>['Maize', 'Beans', 'Cassava'];
  final _alerts = <String>[];
  bool _loading = false;
  bool _isLive = false;
  bool _everLoaded = false;

  Future<void> _refresh() async {
    setState(() {
      _loading = true;
      _alerts.clear();
    });
    final api = context.read<ApiService>();
    var sawLive = false;
    for (final crop in _watchlist) {
      try {
        final source = LiveFlag();
        final fc = await api.getForecast(commodity: crop, horizon: 14, source: source);
        if (source.value) sawLive = true;
        if (fc.alert != null && fc.alert!.isNotEmpty) {
          _alerts.add('${fc.commodity} (${fc.market}): ${fc.alert}');
        } else if (fc.pctChange.abs() >= 5) {
          final dir = fc.pctChange > 0 ? 'up' : 'down';
          _alerts.add(
            '${fc.commodity}: expected to move $dir ${fc.pctChange.abs().toStringAsFixed(1)}% in ${fc.horizonDays}d',
          );
        }
      } catch (_) {
        // skip offline / missing
      }
    }
    setState(() {
      _loading = false;
      _isLive = sawLive;
      _everLoaded = true;
    });
  }

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('🔔 Alerts'),
        actions: [
          if (_everLoaded) DataSourceChip(isLive: _isLive),
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loading ? null : _refresh,
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _alerts.isEmpty
              ? const Center(
                  child: Text(
                    'No significant price alerts right now.\nPull to refresh.',
                    textAlign: TextAlign.center,
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _refresh,
                  child: ListView.separated(
                    padding: const EdgeInsets.all(16),
                    itemCount: _alerts.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 8),
                    itemBuilder: (context, i) {
                      return Card(
                        child: ListTile(
                          leading: const Icon(Icons.warning_amber_rounded),
                          title: Text(_alerts[i]),
                        ),
                      );
                    },
                  ),
                ),
    );
  }
}
