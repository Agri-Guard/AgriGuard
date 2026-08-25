import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/market_model.dart';
import '../services/api_service.dart';
import '../widgets/data_source_chip.dart';

class MarketScreen extends StatefulWidget {
  const MarketScreen({super.key});

  @override
  State<MarketScreen> createState() => _MarketScreenState();
}

class _MarketScreenState extends State<MarketScreen> {
  String _commodity = 'Maize';
  CommodityMarketSummary? _summary;
  TopMoversResponse? _movers;
  List<ArbitrageOpportunity>? _arbitrage;
  String? _arbitrageNotice; // set instead of _error for the expected 404/422 cases
  bool _loading = false;
  String? _error;
  bool _isLive = false;

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = context.read<ApiService>();
      // Fetch the cross-market summary, the national movers feed, and
      // arbitrage pairs together — one failing shouldn't blank the others,
      // so they're awaited independently below rather than via Future.wait
      // (which fails fast on the first rejection). Each gets its own
      // LiveFlag rather than sharing one on ApiService, since these three
      // requests are genuinely concurrent — a shared flag would race.
      final summarySource = LiveFlag();
      final summaryFuture = api.marketSummary(_commodity, source: summarySource);
      final moversFuture = api.topMovers(periodDays: 30, topN: 5);
      final arbitrageFuture = api.arbitrageOpportunities(commodity: _commodity);

      CommodityMarketSummary? summary;
      TopMoversResponse? movers;
      List<ArbitrageOpportunity>? arbitrage;
      String? error;
      String? arbitrageNotice;

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
      try {
        arbitrage = await arbitrageFuture;
      } on ApiException catch (e) {
        // 404 (nothing above the margin threshold) and 422 (fewer than 2
        // markets have data) are expected, non-error outcomes for this
        // endpoint — show a plain notice instead of the red error state.
        if (e.statusCode == 404) {
          arbitrageNotice = 'No strong arbitrage opportunities for $_commodity right now.';
        } else if (e.statusCode == 422) {
          arbitrageNotice = 'Not enough $_commodity price data across markets yet.';
        } else {
          arbitrageNotice = 'Could not load arbitrage data: ${e.body}';
        }
      } catch (_) {
        arbitrageNotice = 'Could not load arbitrage data.';
      }

      setState(() {
        _summary = summary;
        _movers = movers;
        _arbitrage = arbitrage;
        _arbitrageNotice = arbitrageNotice;
        _error = error;
        _isLive = summarySource.value;
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
      appBar: AppBar(
        title: const Text('🏪 Market Intelligence'),
        actions: [
          if (_summary != null || _error != null) DataSourceChip(isLive: _isLive),
        ],
      ),
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
            ..._buildArbitrageSection(),
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

  /// GET /markets/arbitrage/{commodity} — every buy/sell market pair with a
  /// gross margin, ranked biggest first. More actionable than the plain
  /// best/worst-market metric in [_buildSummarySection] above: this shows
  /// every pair worth considering, not just the two extremes, and carries
  /// the backend's own viability call and transport-cost caveat per pair.
  List<Widget> _buildArbitrageSection() {
    if (_arbitrage == null || _arbitrage!.isEmpty) {
      if (_arbitrageNotice == null) return const [];
      return [
        const SizedBox(height: 24),
        Text('💰 Arbitrage Opportunities', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        Text(_arbitrageNotice!, style: TextStyle(color: Theme.of(context).colorScheme.outline)),
      ];
    }

    return [
      const SizedBox(height: 24),
      Text('💰 Arbitrage Opportunities', style: Theme.of(context).textTheme.titleMedium),
      const SizedBox(height: 4),
      Text(
        'Gross margin only — always weigh it against actual transport cost.',
        style: Theme.of(context).textTheme.bodySmall,
      ),
      const SizedBox(height: 8),
      ..._arbitrage!.take(5).map(_arbitrageTile),
    ];
  }

  Widget _arbitrageTile(ArbitrageOpportunity o) {
    return Card(
      child: ListTile(
        leading: Icon(
          o.viable ? Icons.check_circle_outline : Icons.warning_amber_outlined,
          color: o.viable ? Colors.green : Colors.orange,
        ),
        title: Text('${o.buyMarket} → ${o.sellMarket}'),
        subtitle: Text(
          '${_fmtPrice(o.buyPrice, o.currency, o.unit)} → ${_fmtPrice(o.sellPrice, o.currency, o.unit)}\n${o.note}',
        ),
        isThreeLine: true,
        trailing: Text(
          '+${o.grossMarginPct.toStringAsFixed(1)}%',
          style: TextStyle(fontWeight: FontWeight.w700, color: o.viable ? Colors.green : Colors.orange),
        ),
      ),
    );
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
