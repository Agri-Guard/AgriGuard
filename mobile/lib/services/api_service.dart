import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/forecast_model.dart';
import '../models/market_model.dart';

/// Thin HTTP client for the AgriGuard FastAPI backend.
class ApiService {
  final String baseUrl;

  /// Resolved once at build/run time from --dart-define=API_BASE_URL=....
  /// Falls back to the Android Emulator's host alias when not supplied,
  /// which is only valid on the emulator — never on a real device.
  static const String _envBaseUrl = String.fromEnvironment('API_BASE_URL');

  ApiService({
    String? baseUrl,
  }) : baseUrl = baseUrl ??
            (_envBaseUrl.isNotEmpty ? _envBaseUrl : 'http://10.0.2.2:8000');

  Future<Map<String, dynamic>> _get(String path, [Map<String, String>? query]) async {
    final uri = Uri.parse('$baseUrl$path').replace(queryParameters: query);
    final res = await http.get(uri).timeout(const Duration(seconds: 25));
    if (res.statusCode >= 400) {
      throw ApiException(res.statusCode, res.body);
    }
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  /// Same as [_get], for endpoints whose response body is a bare JSON array
  /// rather than an object (e.g. GET /markets/arbitrage/{commodity}).
  Future<List<dynamic>> _getList(String path, [Map<String, String>? query]) async {
    final uri = Uri.parse('$baseUrl$path').replace(queryParameters: query);
    final res = await http.get(uri).timeout(const Duration(seconds: 25));
    if (res.statusCode >= 400) {
      throw ApiException(res.statusCode, res.body);
    }
    return jsonDecode(res.body) as List<dynamic>;
  }

  Future<bool> health() async {
    try {
      final data = await _get('/health');
      return data['status'] == 'ok';
    } catch (_) {
      return false;
    }
  }

  Future<CommodityList> listCommodities() async {
    final data = await _get('/forecasts/commodities');
    return CommodityList.fromJson(data);
  }

  Future<ForecastResponse> getForecast({
    required String commodity,
    String market = 'Kampala',
    int horizon = 14,
  }) async {
    final data = await _get(
      '/forecasts/${Uri.encodeComponent(commodity)}',
      {'market': market, 'horizon': '$horizon'},
    );
    return ForecastResponse.fromJson(data);
  }

  Future<List<HistoryPoint>> getHistory({
    required String commodity,
    String market = 'Kampala',
    int days = 180,
  }) async {
    final data = await _get(
      '/forecasts/history/${Uri.encodeComponent(commodity)}',
      {'market': market, 'days': '$days'},
    );
    final list = data['history'] as List<dynamic>;
    return list
        .map((e) => HistoryPoint.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// GET /markets/summary/{commodity} — cross-market comparison for one
  /// commodity: best/worst market to sell in, national average, and a
  /// plain-language recommendation. See CommodityMarketSummary for the
  /// exact field names this maps from (they don't include top-level
  /// "best_price"/"worst_price" — those are derived on the model itself).
  Future<CommodityMarketSummary> marketSummary(String commodity) async {
    final data = await _get('/markets/summary/${Uri.encodeComponent(commodity)}');
    return CommodityMarketSummary.fromJson(data);
  }

  /// GET /markets/movers — biggest price gainers and losers across all
  /// commodities and markets over `periodDays`.
  Future<TopMoversResponse> topMovers({int periodDays = 30, int topN = 5}) async {
    final data = await _get('/markets/movers', {
      'period_days': '$periodDays',
      'top_n': '$topN',
    });
    return TopMoversResponse.fromJson(data);
  }

  Future<Map<String, dynamic>> nationalSummary() async {
    return _get('/markets/national-summary');
  }

  /// GET /markets/arbitrage/{commodity} — every buy/sell market pair with a
  /// gross margin above [minMarginPct], sorted biggest opportunity first.
  /// The backend raises 404 when nothing clears the threshold and 422 when
  /// fewer than 2 of the requested markets have price data — both are
  /// expected outcomes here, not failures, so callers should check for
  /// those status codes on the thrown [ApiException] rather than treating
  /// every error the same way (see market_screen.dart for the pattern).
  Future<List<ArbitrageOpportunity>> arbitrageOpportunities({
    required String commodity,
    String markets = 'Kampala,Mbarara,Gulu,Kabale,Jinja,Mbale',
    double minMarginPct = 10.0,
  }) async {
    final data = await _getList(
      '/markets/arbitrage/${Uri.encodeComponent(commodity)}',
      {'markets': markets, 'min_margin_pct': '$minMarginPct'},
    );
    return data
        .map((e) => ArbitrageOpportunity.fromJson(e as Map<String, dynamic>))
        .toList();
  }
}

class ApiException implements Exception {
  final int statusCode;
  final String body;
  ApiException(this.statusCode, this.body);

  @override
  String toString() => 'ApiException($statusCode): $body';
}