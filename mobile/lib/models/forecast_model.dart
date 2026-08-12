/// Data classes mirroring the AgriGuard FastAPI forecast schemas.

class ForecastPoint {
  final String date;
  final double predictedPrice;
  final double lowerBound;
  final double upperBound;
  final double confidence;

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

class ForecastResponse {
  final String commodity;
  final String market;
  final String currency;
  final String unit;
  final int horizonDays;
  final int observationsUsed;
  final List<ForecastPoint> forecast;
  final String trend;
  final double pctChange;
  final String? alert;
  final String modelUsed;
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
    final points = (json['forecast'] as List<dynamic>)
        .map((e) => ForecastPoint.fromJson(e as Map<String, dynamic>))
        .toList();
    return ForecastResponse(
      commodity: json['commodity'] as String,
      market: json['market'] as String,
      currency: json['currency'] as String? ?? 'UGX',
      unit: json['unit'] as String? ?? 'KG',
      horizonDays: json['horizon_days'] as int,
      observationsUsed: json['observations_used'] as int,
      forecast: points,
      trend: json['trend'] as String,
      pctChange: (json['pct_change'] as num).toDouble(),
      alert: json['alert'] as String?,
      modelUsed: json['model_used'] as String? ?? 'unknown',
      generatedAt: json['generated_at'] as String? ?? '',
    );
  }

  double get lastPredicted =>
      forecast.isNotEmpty ? forecast.last.predictedPrice : 0.0;
}

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
      commodities: List<String>.from(json['commodities'] as List),
      markets: List<String>.from(json['markets'] as List),
      totalObservations: json['total_observations'] as int,
    );
  }
}

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
