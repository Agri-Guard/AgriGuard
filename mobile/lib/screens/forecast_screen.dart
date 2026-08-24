import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:intl/intl.dart';

import '../services/api_service.dart';
import '../models/forecast_model.dart';
import '../widgets/forecast_card.dart';
import '../offline/local_cache.dart';

class ForecastScreen extends StatefulWidget {
  const ForecastScreen({super.key});

  @override
  State<ForecastScreen> createState() => _ForecastScreenState();
}

class _ForecastScreenState extends State<ForecastScreen> {
  final _commodityCtrl = TextEditingController(text: 'Maize');
  final _marketCtrl = TextEditingController(text: 'Kampala');
  int _horizon = 14;
  ForecastResponse? _forecast;
  List<HistoryPoint> _history = [];
  bool _loading = false;
  String? _error;
  bool _fromCache = false;

  @override
  void dispose() {
    _commodityCtrl.dispose();
    _marketCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final commodity = _commodityCtrl.text.trim().isEmpty
        ? 'Maize'
        : _commodityCtrl.text.trim();
    final market =
        _marketCtrl.text.trim().isEmpty ? 'Kampala' : _marketCtrl.text.trim();

    setState(() {
      _loading = true;
      _error = null;
      _fromCache = false;
    });
    try {
      final api = context.read<ApiService>();
      final fc = await api.getForecast(
        commodity: commodity,
        market: market,
        horizon: _horizon,
      );
      List<HistoryPoint> hist = [];
      try {
        hist = await api.getHistory(
          commodity: commodity,
          market: market,
          days: 90,
        );
      } catch (_) {
        // history is optional
      }
      setState(() {
        _forecast = fc;
        _history = hist;
      });
    } catch (e) {
      // Network/API call failed — fall back to whatever HomeShell's
      // background sync last cached for this commodity/market before
      // surfacing a hard error, so a lost connection doesn't leave the
      // screen blank if we have something recent to show.
      final cached = await context.read<LocalCache>().get(
            'forecast_${commodity}_$market',
          );
      if (cached != null) {
        setState(() {
          _forecast = _forecastFromCache(cached);
          _history = [];
          _fromCache = true;
        });
      } else {
        setState(() => _error = e.toString());
      }
    } finally {
      setState(() => _loading = false);
    }
  }

  /// Rebuilds a display-ready [ForecastResponse] from the compact map
  /// [SyncService.prefetch] stores offline. The cache only keeps the
  /// headline numbers (not the full point-by-point horizon), so this
  /// produces a single synthetic [ForecastPoint] carrying the last known
  /// price — enough for [ForecastCard] to render correctly, including
  /// [ForecastResponse.lastPredicted], without pretending we have a full
  /// forecast curve to chart.
  ForecastResponse _forecastFromCache(Map<String, dynamic> cached) {
    final lastPrice = (cached['last_price'] as num?)?.toDouble() ?? 0.0;
    final cachedAt = cached['cached_at'] as String? ?? '';
    return ForecastResponse(
      commodity: cached['commodity'] as String? ?? '',
      market: cached['market'] as String? ?? '',
      currency: 'UGX',
      unit: 'KG',
      horizonDays: _horizon,
      observationsUsed: 0,
      forecast: [
        ForecastPoint(
          date: cachedAt,
          predictedPrice: lastPrice,
          lowerBound: lastPrice,
          upperBound: lastPrice,
          confidence: 1.0,
        ),
      ],
      trend: cached['trend'] as String? ?? 'stable',
      pctChange: (cached['pct_change'] as num?)?.toDouble() ?? 0.0,
      alert: cached['alert'] as String?,
      modelUsed: 'cached',
      generatedAt: cachedAt,
    );
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('📈 Price Forecast'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loading ? null : _load,
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(
            controller: _commodityCtrl,
            decoration: const InputDecoration(
              labelText: 'Commodity',
              border: OutlineInputBorder(),
              hintText: 'e.g. Maize, Beans, Cassava',
            ),
            textInputAction: TextInputAction.next,
            onSubmitted: (_) => _load(),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _marketCtrl,
            decoration: const InputDecoration(
              labelText: 'Market',
              border: OutlineInputBorder(),
              hintText: 'e.g. Kampala, Gulu',
            ),
            textInputAction: TextInputAction.done,
            onSubmitted: (_) => _load(),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: InputDecorator(
                  decoration: const InputDecoration(
                    labelText: 'Horizon (days)',
                    border: OutlineInputBorder(),
                  ),
                  child: DropdownButtonHideUnderline(
                    child: DropdownButton<int>(
                      value: _horizon,
                      isExpanded: true,
                      items: const [
                        DropdownMenuItem(value: 7, child: Text('7 days')),
                        DropdownMenuItem(value: 14, child: Text('14 days')),
                        DropdownMenuItem(value: 28, child: Text('28 days')),
                      ],
                      onChanged: (v) {
                        if (v != null) setState(() => _horizon = v);
                      },
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              FilledButton(
                onPressed: _loading ? null : _load,
                child: Text(_loading ? 'Loading…' : 'Forecast'),
              ),
            ],
          ),
          const SizedBox(height: 16),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ),
          if (_loading)
            const Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: CircularProgressIndicator(),
              ),
            ),
          if (_fromCache && _forecast != null && !_loading)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    Icon(Icons.cloud_off, size: 16, color: Theme.of(context).colorScheme.outline),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Offline — showing the last synced price, not a live forecast curve.',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          if (_forecast != null && !_loading) ...[
            ForecastCard(forecast: _forecast!),
            const SizedBox(height: 16),
            if (!_fromCache && (_history.isNotEmpty || _forecast!.forecast.isNotEmpty))
              _buildChart(context),
            const SizedBox(height: 16),
            Text(
              'Forecast points',
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
            ),
            const SizedBox(height: 8),
            Card(
              child: Column(
                children: _forecast!.forecast
                    .map(
                      (p) => ForecastPointTile(
                        point: p,
                        currency: _forecast!.currency,
                        unit: _forecast!.unit,
                      ),
                    )
                    .toList(),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildChart(BuildContext context) {
    final spots = <FlSpot>[];
    final labels = <String>[];
    var i = 0.0;

    final hist = _history.length > 30
        ? _history.sublist(_history.length - 30)
        : _history;
    for (final h in hist) {
      spots.add(FlSpot(i, h.price));
      labels.add(h.date);
      i += 1;
    }
    final histEnd = i;

    for (final p in _forecast!.forecast) {
      spots.add(FlSpot(i, p.predictedPrice));
      labels.add(p.date);
      i += 1;
    }

    if (spots.isEmpty) return const SizedBox.shrink();

    final minY = spots.map((s) => s.y).reduce((a, b) => a < b ? a : b) * 0.95;
    final maxY = spots.map((s) => s.y).reduce((a, b) => a > b ? a : b) * 1.05;

    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(8, 16, 16, 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Price trend (UGX)',
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
            ),
            const SizedBox(height: 12),
            SizedBox(
              height: 220,
              child: LineChart(
                LineChartData(
                  minY: minY,
                  maxY: maxY,
                  gridData: const FlGridData(show: true, drawVerticalLine: false),
                  borderData: FlBorderData(show: false),
                  titlesData: FlTitlesData(
                    leftTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        reservedSize: 44,
                        getTitlesWidget: (v, _) => Text(
                          NumberFormat.compact().format(v),
                          style: const TextStyle(fontSize: 10),
                        ),
                      ),
                    ),
                    bottomTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        // clamp() on a double returns num, not double —
                        // needs an explicit toDouble() for the double?
                        // param below.
                        interval: (spots.length / 4)
                            .ceilToDouble()
                            .clamp(1, 10)
                            .toDouble(),
                        getTitlesWidget: (v, _) {
                          final idx = v.toInt();
                          if (idx < 0 || idx >= labels.length) {
                            return const SizedBox.shrink();
                          }
                          final d = labels[idx];
                          final short = d.length >= 10 ? d.substring(5, 10) : d;
                          return Padding(
                            padding: const EdgeInsets.only(top: 4),
                            child: Text(short, style: const TextStyle(fontSize: 9)),
                          );
                        },
                      ),
                    ),
                    topTitles: const AxisTitles(
                      sideTitles: SideTitles(showTitles: false),
                    ),
                    rightTitles: const AxisTitles(
                      sideTitles: SideTitles(showTitles: false),
                    ),
                  ),
                  lineBarsData: [
                    LineChartBarData(
                      spots: spots.where((s) => s.x < histEnd).toList(),
                      isCurved: true,
                      color: Theme.of(context).colorScheme.primary,
                      barWidth: 2.5,
                      dotData: const FlDotData(show: false),
                      belowBarData: BarAreaData(
                        show: true,
                        // .withOpacity(), not .withValues() — the latter needs
                        // Flutter 3.27+ and CI is pinned to 3.24.x.
                        color: Theme.of(context)
                            .colorScheme
                            .primary
                            .withOpacity(0.12),
                      ),
                    ),
                    if (histEnd < spots.length)
                      LineChartBarData(
                        spots: spots.where((s) => s.x >= histEnd - 1).toList(),
                        isCurved: true,
                        color: Colors.orange.shade700,
                        barWidth: 2.5,
                        dashArray: const [6, 4],
                        dotData: const FlDotData(show: true),
                      ),
                  ],
                  lineTouchData: LineTouchData(
                    touchTooltipData: LineTouchTooltipData(
                      getTooltipItems: (touched) {
                        return touched.map((t) {
                          final idx = t.x.toInt();
                          final label = idx >= 0 && idx < labels.length
                              ? labels[idx]
                              : '';
                          return LineTooltipItem(
                            '$label\n${t.y.toStringAsFixed(0)} UGX',
                            const TextStyle(color: Colors.white, fontSize: 12),
                          );
                        }).toList();
                      },
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 4),
            Row(
              children: [
                _legendDot(Theme.of(context).colorScheme.primary, 'History'),
                const SizedBox(width: 16),
                _legendDot(Colors.orange.shade700, 'Forecast'),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _legendDot(Color color, String label) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 4),
        Text(label, style: const TextStyle(fontSize: 11)),
      ],
    );
  }
}
