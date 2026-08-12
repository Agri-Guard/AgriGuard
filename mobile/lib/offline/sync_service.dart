import 'package:connectivity_plus/connectivity_plus.dart';
import '../services/api_service.dart';
import 'local_cache.dart';

/// Background-friendly sync that refreshes the most-used commodities
/// when connectivity is available and stores them offline.
class SyncService {
  final ApiService api;
  final LocalCache cache;

  SyncService({required this.api, required this.cache});

  Future<bool> get isOnline async {
    final result = await Connectivity().checkConnectivity();
    return !result.contains(ConnectivityResult.none);
  }

  /// Prefetch forecasts for a list of (commodity, market) pairs.
  Future<int> prefetch(List<(String, String)> pairs, {int horizon = 14}) async {
    if (!await isOnline) return 0;
    var ok = 0;
    for (final (commodity, market) in pairs) {
      try {
        final forecast = await api.getForecast(
          commodity: commodity,
          market: market,
          horizon: horizon,
        );
        await cache.put(
          'forecast_${commodity}_$market',
          {
            'commodity': forecast.commodity,
            'market': forecast.market,
            'last_price': forecast.lastPredicted,
            'trend': forecast.trend,
            'pct_change': forecast.pctChange,
            'alert': forecast.alert,
            'cached_at': DateTime.now().toIso8601String(),
          },
        );
        ok++;
      } catch (_) {
        // keep going
      }
    }
    return ok;
  }
}
