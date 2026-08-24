/// Data classes mirroring the AgriGuard FastAPI forecasting schemas
/// (backend/app/routers/forecasts.py). Field names below are the camelCase
/// Dart-side names; `fromJson` maps them from the snake_case JSON keys the
/// backend actually returns — keep these in sync with forecasts.py if its
/// Pydantic models change.

/// A single predicted price point on the forecast horizon.
/// Mirrors routers/forecasts.py::ForecastPoint.
class ForecastPoint {
  final String date;
  final double predictedPrice;
  final double lowerBound; // Lower edge of 90% prediction interval
  final double upperBound; // Upper edge of 90% prediction interval
  final double confidence; // Clamped to [0.0, 1.0]

  ForecastPoint({
    required this.date,
    required this.predictedPrice,
    required this.lowerBound,
    required this.upperBound,
    required this.confidence,
  });

  factory ForecastPoint.fromJson(Map<String, dynamic> json) {
    return ForecastPoint(
      date: json['date'] as String,
      predictedPrice: (json['predicted_price'] as num).toDouble(),
      lowerBound: (json['lower_bound'] as num).toDouble(),
      upperBound: (json['upper_bound'] as num).toDouble(),
      confidence: (json['confidence'] as num).toDouble(),
    );
  }
}

/// Full forecast for one commodity x market combination.
/// Mirrors routers/forecasts.py::ForecastResponse.
class ForecastResponse {
  final String commodity;
  final String market;
  final String currency;
  final String unit;
  final int horizonDays;
  final int observationsUsed;
  final List<ForecastPoint> forecast;
  final String trend; // "rising" | "falling" | "stable"
  final double pctChange;
  final String? alert;
  final String modelUsed; // "prophet" | "prophet+xgb" | "linear"
  final String generatedAt;

  ForecastResponse({
    required this.commodity,
    required this.market,
    required this.currency,
    required this.unit,
    required this.horizonDays,
    required this.observationsUsed,
    required this.forecast,
    required this.trend,
    required this.pctChange,
    this.alert,
    required this.modelUsed,
    required this.generatedAt,
  });

  factory ForecastResponse.fromJson(Map<String, dynamic> json) {
    return ForecastResponse(
      commodity: json['commodity'] as String,
      market: json['market'] as String,
      currency: json['currency'] as String? ?? 'UGX',
      unit: json['unit'] as String? ?? 'KG',
      horizonDays: json['horizon_days'] as int? ?? 0,
      observationsUsed: json['observations_used'] as int? ?? 0,
      forecast: (json['forecast'] as List<dynamic>? ?? [])
          .map((e) => ForecastPoint.fromJson(e as Map<String, dynamic>))
          .toList(),
      trend: json['trend'] as String? ?? 'stable',
      pctChange: (json['pct_change'] as num?)?.toDouble() ?? 0.0,
      alert: json['alert'] as String?,
      modelUsed: json['model_used'] as String? ?? 'linear',
      generatedAt: json['generated_at'] as String? ?? '',
    );
  }

  /// Convenience accessor for the UI: the last (furthest-out) predicted
  /// price in the horizon. The backend has no single "last predicted"
  /// field of its own — this is derived client-side from [forecast].
  double get lastPredicted => forecast.isEmpty ? 0.0 : forecast.last.predictedPrice;
}

/// Available commodities and markets in the loaded dataset.
/// Mirrors routers/forecasts.py::CommodityListResponse.
class CommodityList {
  final List<String> commodities;
  final List<String> markets;
  final int totalObservations;

  CommodityList({
    required this.commodities,
    required this.markets,
    required this.totalObservations,
  });

  factory CommodityList.fromJson(Map<String, dynamic> json) {
    return CommodityList(
      commodities: (json['commodities'] as List<dynamic>? ?? [])
          .map((e) => e as String)
          .toList(),
      markets: (json['markets'] as List<dynamic>? ?? [])
          .map((e) => e as String)
          .toList(),
      totalObservations: json['total_observations'] as int? ?? 0,
    );
  }
}

/// A single historical price observation (for sparklines / charts).
/// Mirrors routers/forecasts.py::HistoryPoint.
class HistoryPoint {
  final String date;
  final double price;

  HistoryPoint({required this.date, required this.price});

  factory HistoryPoint.fromJson(Map<String, dynamic> json) {
    return HistoryPoint(
      date: json['date'] as String,
      price: (json['price'] as num).toDouble(),
    );
  }
}
