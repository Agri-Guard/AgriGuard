import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/forecast_model.dart';
import '../models/market_model.dart';

/// Thin HTTP client for the AgriGuard FastAPI backend.
class ApiService {
  final String baseUrl;

  ApiService({this.baseUrl = 'http://10.0.2.2:8000'}); // Android emulator → host

  Future<Map<String, dynamic>> _get(String path, [Map<String, String>? query]) async {
    final uri = Uri.parse('$baseUrl$path').replace(queryParameters: query);
    final res = await http.get(uri).timeout(const Duration(seconds: 25));
    if (res.statusCode >= 400) {
      throw ApiException(res.statusCode, res.body);
    }
    return jsonDecode(res.body) as Map<String, dynamic>;
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
}

class ApiException implements Exception {
  final int statusCode;
  final String body;
  ApiException(this.statusCode, this.body);

  @override
  String toString() => 'ApiException($statusCode): $body';
}