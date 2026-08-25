import 'dart:convert';
import 'package:flutter/services.dart' show rootBundle;
import '../models/forecast_model.dart';
import '../models/market_model.dart';

/// Fully offline data source — no HTTP, no backend, ever.
///
/// Keith's PC (where the FastAPI backend normally runs) isn't reachable
/// while he's out on mobile data, so the whole "point the app at a live
/// server" approach (LAN IP, network security config, INTERNET permission)
/// is out. Instead the same commodity/market/arbitrage numbers the backend
/// would compute are precomputed once (see gen_offline_data.py, run against
/// the exact same algorithms as backend/app/routers/forecasts.py and
/// markets.py) and bundled into the APK as assets/data/agriguard_offline_data.json.
/// This class keeps the ApiService name and every method signature from the
/// old HTTP client so ForecastScreen/MarketScreen/AlertsScreen don't need to
/// change at all — only what's behind the interface changed.
///
/// Trade-off (confirmed with Keith): forecasts and prices are a snapshot as
/// of whenever gen_offline_data.py was last run, not live. Re-run it and
/// rebuild the APK to refresh the bundled numbers.
class ApiService {
  static const String _assetPath = 'assets/data/agriguard_offline_data.json';
  static Map<String, dynamic>? _cache;

  Future<Map<String, dynamic>> _data() async {
    if (_cache != null) return _cache!;
    final raw = await rootBundle.loadString(_assetPath);
    _cache = jsonDecode(raw) as Map<String, dynamic>;
    return _cache!;
  }

  /// Case/whitespace-insensitive match against the bundled commodity or
  /// market name list — mirrors the backend's `.strip().title()` normalisation
  /// so a user typing "maize" or " Maize " still resolves.
  String? _resolve(String input, List<String> options) {
    final target = input.trim().toLowerCase();
    for (final o in options) {
      if (o.toLowerCase() == target) return o;
    }
    return null;
  }

  Future<bool> health() async => true; // always "up" — there's no server to be down.

  Future<CommodityList> listCommodities() async {
    final d = await _data();
    final commodities = (d['commodities'] as List<dynamic>).cast<String>();
    final markets = (d['markets'] as List<dynamic>).cast<String>();
    return CommodityList(
      commodities: commodities,
      markets: markets,
      totalObservations: (d['forecasts'] as Map<String, dynamic>).length,
    );
  }

  Future<ForecastResponse> getForecast({
    required String commodity,
    String market = 'Kampala',
    int horizon = 14,
  }) async {
    final d = await _data();
    final forecasts = d['forecasts'] as Map<String, dynamic>;
    final commodities = (d['commodities'] as List<dynamic>).cast<String>();

    final resolvedCommodity = _resolve(commodity, commodities) ?? commodity.trim();
    // Exact commodity+market key first; otherwise any market with data for
    // this commodity, mirroring the backend's fallback chain in _filter_subset().
    var key = '$resolvedCommodity|${market.trim()}';
    if (!forecasts.containsKey(key)) {
      final fallbackKey = forecasts.keys.firstWhere(
        (k) => k.startsWith('$resolvedCommodity|'),
        orElse: () => '',
      );
      if (fallbackKey.isEmpty) {
        throw ApiException(404, 'No price data found for "$commodity".');
      }
      key = fallbackKey;
    }
    final entry = forecasts[key] as Map<String, dynamic>;
    final horizons = entry['horizons'] as Map<String, dynamic>;

    // Bundled data only precomputed 7/14/28-day horizons — snap to the
    // nearest available one rather than erroring on an odd value.
    final available = horizons.keys.map(int.parse).toList()..sort();
    final chosen = available.reduce(
      (a, b) => (a - horizon).abs() <= (b - horizon).abs() ? a : b,
    );
    return ForecastResponse.fromJson(horizons['$chosen'] as Map<String, dynamic>);
  }

  Future<List<HistoryPoint>> getHistory({
    required String commodity,
    String market = 'Kampala',
    int days = 180,
  }) async {
    final d = await _data();
    final forecasts = d['forecasts'] as Map<String, dynamic>;
    final commodities = (d['commodities'] as List<dynamic>).cast<String>();
    final resolvedCommodity = _resolve(commodity, commodities) ?? commodity.trim();

    var key = '$resolvedCommodity|${market.trim()}';
    if (!forecasts.containsKey(key)) {
      final fallbackKey = forecasts.keys.firstWhere(
        (k) => k.startsWith('$resolvedCommodity|'),
        orElse: () => '',
      );
      if (fallbackKey.isEmpty) return [];
      key = fallbackKey;
    }
    final entry = forecasts[key] as Map<String, dynamic>;
    final hist = (entry['history'] as List<dynamic>)
        .map((e) => HistoryPoint.fromJson(e as Map<String, dynamic>))
        .toList();
    return hist;
  }

  Future<CommodityMarketSummary> marketSummary(String commodity) async {
    final d = await _data();
    final summaries = d['market_summaries'] as Map<String, dynamic>;
    final commodities = (d['commodities'] as List<dynamic>).cast<String>();
    final resolved = _resolve(commodity, commodities) ?? commodity.trim();
    if (!summaries.containsKey(resolved)) {
      throw ApiException(404, 'No market data found for "$commodity".');
    }
    return CommodityMarketSummary.fromJson(summaries[resolved] as Map<String, dynamic>);
  }

  Future<TopMoversResponse> topMovers({int periodDays = 30, int topN = 5}) async {
    final d = await _data();
    final movers = d['top_movers'] as Map<String, dynamic>;
    // Bundled data was precomputed for a fixed 30-day window and top-5 —
    // topN just truncates further, periodDays is informational only here.
    final gainers = (movers['gainers'] as List<dynamic>).take(topN).toList();
    final losers = (movers['losers'] as List<dynamic>).take(topN).toList();
    return TopMoversResponse.fromJson({
      'gainers': gainers,
      'losers': losers,
      'period_days': movers['period_days'],
      'generated_at': movers['generated_at'],
    });
  }

  Future<Map<String, dynamic>> nationalSummary() async {
    final d = await _data();
    return {'data_as_of': d['data_as_of'], 'generated_at': d['generated_at']};
  }

  Future<List<ArbitrageOpportunity>> arbitrageOpportunities({
    required String commodity,
    String markets = 'Kampala,Mbarara,Gulu,Kabale,Jinja,Mbale',
    double minMarginPct = 10.0,
  }) async {
    final d = await _data();
    final arbitrage = d['arbitrage'] as Map<String, dynamic>;
    final commodities = (d['commodities'] as List<dynamic>).cast<String>();
    final resolved = _resolve(commodity, commodities) ?? commodity.trim();

    if (!arbitrage.containsKey(resolved)) {
      throw ApiException(
        404,
        'No arbitrage opportunities found for "$commodity" above ${minMarginPct.toStringAsFixed(0)}%.',
      );
    }
    final list = (arbitrage[resolved] as List<dynamic>)
        .map((e) => ArbitrageOpportunity.fromJson(e as Map<String, dynamic>))
        .where((o) => o.grossMarginPct >= minMarginPct)
        .toList();
    if (list.isEmpty) {
      throw ApiException(
        404,
        'No arbitrage opportunities found for "$commodity" above ${minMarginPct.toStringAsFixed(0)}%.',
      );
    }
    return list;
  }
}

class ApiException implements Exception {
  final int statusCode;
  final String body;
  ApiException(this.statusCode, this.body);

  @override
  String toString() => 'ApiException($statusCode): $body';
}
