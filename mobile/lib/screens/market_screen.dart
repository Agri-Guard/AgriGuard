import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/market_model.dart';
import '../services/api_service.dart';

class MarketScreen extends StatefulWidget {
  const MarketScreen({super.key});

  @override
  State<MarketScreen> createState() => _MarketScreenState();
}

class _MarketScreenState extends State<MarketScreen> {
  String _commodity = 'Maize';
  CommodityMarketSummary? _summary;
  TopMoversResponse? _movers;
  bool _loading = false;
  String? _error;

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = context.read<ApiService>();
      // Fetch the cross-market summary for the chosen commodity and the
      // national movers feed together — one failing shouldn't blank the
      // other, so they're awaited independently below rather than via
      // Future.wait (which fails fast on the first rejection).
      final summaryFuture = api.marketSummary(_commodity);
      final moversFuture = api.topMovers(periodDays: 30, topN: 5);

      CommodityMarketSummary? summary;
      TopMoversResponse? movers;
      String? error;

      try {
        summary = await summaryFuture;
      } catch (e) {
        error = e.toString();
      }
      try {
        movers = await moversFuture;
      } catch (_) {
        // Movers are supplementary — a failure here shouldn't block the
        // per-commodity summary from displaying.
      }

      setState(() {
        _summary = summary;
        _movers = movers;
        _error = error;
      });
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
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
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
            if (_summary != null) ..._buildSummarySection(_summary!),
            if (_movers != null) ..._buildMoversSection(_movers!),
          ],
        ),
      ),
    );
  }

  List<Widget> _buildSummarySection(CommodityMarketSummary s) {
    final best = s.bestMarket;
    final worst = s.worstMarket;
    return [
      Text('${s.commodity} — cross-market summary', style: Theme.of(context).textTheme.titleMedium),
      const SizedBox(height: 8),
      _tile('Best market to sell', best == null ? '—' : '${best.market} (${_fmtPrice(best.latestPrice, s.currency, s.unit)})'),
      _tile('Worst market to sell', worst == null ? '—' : '${worst.market} (${_fmtPrice(worst.latestPrice, s.currency, s.unit)})'),
      _tile('National average', _fmtPrice(s.nationalAvgPrice, s.currency, s.unit)),
      _tile('Price spread', '${_fmtPrice(s.priceSpread, s.currency, s.unit)} (${s.priceSpreadPct.toStringAsFixed(1)}%)'),
      if (s.recommendation.isNotEmpty) ...[
        const SizedBox(height: 8),
        Card(
          color: Theme.of(context).colorScheme.surfaceContainerHighest,
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Text(s.recommendation),
          ),
        ),
      ],
      const SizedBox(height: 12),
      // Full per-market breakdown, already sorted highest -> lowest by the
      // backend — matches the ordering shown in the desktop dashboard.
      ...s.markets.map(
        (m) => _tile(
          '${m.market}${m.region != null ? ' · ${m.region}' : ''}',
          '${_fmtPrice(m.latestPrice, m.currency, m.unit)}  ${_trendIcon(m.trend)}'
              '${m.priceChangePct != null ? '  (${m.priceChangePct! >= 0 ? '+' : ''}${m.priceChangePct!.toStringAsFixed(1)}% / 30d)' : ''}',
        ),
      ),
    ];
  }

  List<Widget> _buildMoversSection(TopMoversResponse movers) {
    return [
      const SizedBox(height: 24),
      Text('🔥 Biggest movers — last ${movers.periodDays} days', style: Theme.of(context).textTheme.titleMedium),
      const SizedBox(height: 8),
      if (movers.gainers.isEmpty && movers.losers.isEmpty)
        const Text('No significant price movements right now.'),
      ...movers.gainers.map((g) => _moverTile(g, up: true)),
      ...movers.losers.map((l) => _moverTile(l, up: false)),
    ];
  }

  Widget _moverTile(TopMoverItem m, {required bool up}) {
    final color = up ? Colors.green : Colors.red;
    return Card(
      child: ListTile(
        leading: Icon(up ? Icons.trending_up : Icons.trending_down, color: color),
        title: Text('${m.commodity} in ${m.market}'),
        subtitle: Text('Alert: ${m.alertLevel}'),
        trailing: Text(
          '${m.changePct >= 0 ? '+' : ''}${m.changePct.toStringAsFixed(1)}%',
          style: TextStyle(fontWeight: FontWeight.w700, color: color),
        ),
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

  String _fmtPrice(double price, String currency, String unit) =>
      '$currency ${price.toStringAsFixed(0)}/$unit';

  String _trendIcon(String trend) {
    switch (trend) {
      case 'rising':
        return '📈';
      case 'falling':
        return '📉';
      default:
        return '➡️';
    }
  }
}
