/// Data classes mirroring the AgriGuard FastAPI weather schemas
/// (backend/app/routers/weather.py, backend/app/schemas/weather.py).
/// Only the two analytics endpoints that need no market_id lookup are
/// modelled here — drought risk and heavy-rain alerts — since every other
/// screen in this app already addresses markets by name, not numeric id,
/// and these two endpoints are the ones that match that pattern.

class DroughtRiskItem {
  final int marketId;
  final String marketName;
  final String region;
  final int deficitDays;
  final int lookbackDays;
  final double? avgWaterBalanceMm;
  final String? latestReadingDate;
  final String riskLevel; // "LOW" | "MODERATE" | "HIGH" | "SEVERE"

  DroughtRiskItem({
    required this.marketId,
    required this.marketName,
    required this.region,
    required this.deficitDays,
    required this.lookbackDays,
    this.avgWaterBalanceMm,
    this.latestReadingDate,
    required this.riskLevel,
  });

  factory DroughtRiskItem.fromJson(Map<String, dynamic> json) {
    return DroughtRiskItem(
      marketId: json['market_id'] as int,
      marketName: json['market_name'] as String? ?? '',
      region: json['region'] as String? ?? '',
      deficitDays: json['deficit_days'] as int? ?? 0,
      lookbackDays: json['lookback_days'] as int? ?? 30,
      avgWaterBalanceMm: (json['avg_water_balance_mm'] as num?)?.toDouble(),
      latestReadingDate: json['latest_reading_date'] as String?,
      riskLevel: json['risk_level'] as String? ?? 'LOW',
    );
  }
}

class DroughtRiskResponse {
  final String generatedForDate;
  final double thresholdMm;
  final int lookbackDays;
  final List<DroughtRiskItem> markets;

  DroughtRiskResponse({
    required this.generatedForDate,
    required this.thresholdMm,
    required this.lookbackDays,
    required this.markets,
  });

  factory DroughtRiskResponse.fromJson(Map<String, dynamic> json) {
    return DroughtRiskResponse(
      generatedForDate: json['generated_for_date'] as String? ?? '',
      thresholdMm: (json['threshold_mm'] as num?)?.toDouble() ?? 0.0,
      lookbackDays: json['lookback_days'] as int? ?? 30,
      markets: (json['markets'] as List<dynamic>? ?? [])
          .map((e) => DroughtRiskItem.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}

class HeavyRainAlertItem {
  final int marketId;
  final String marketName;
  final String region;
  final String readingDate;
  final double rainfallMm;
  final bool isForecast;

  HeavyRainAlertItem({
    required this.marketId,
    required this.marketName,
    required this.region,
    required this.readingDate,
    required this.rainfallMm,
    required this.isForecast,
  });

  factory HeavyRainAlertItem.fromJson(Map<String, dynamic> json) {
    return HeavyRainAlertItem(
      marketId: json['market_id'] as int,
      marketName: json['market_name'] as String? ?? '',
      region: json['region'] as String? ?? '',
      readingDate: json['reading_date'] as String? ?? '',
      rainfallMm: (json['rainfall_mm'] as num?)?.toDouble() ?? 0.0,
      isForecast: json['is_forecast'] as bool? ?? false,
    );
  }
}

class HeavyRainAlertResponse {
  final double thresholdMm;
  final int lookbackDays;
  final List<HeavyRainAlertItem> alerts;

  HeavyRainAlertResponse({
    required this.thresholdMm,
    required this.lookbackDays,
    required this.alerts,
  });

  factory HeavyRainAlertResponse.fromJson(Map<String, dynamic> json) {
    return HeavyRainAlertResponse(
      thresholdMm: (json['threshold_mm'] as num?)?.toDouble() ?? 0.0,
      lookbackDays: json['lookback_days'] as int? ?? 7,
      alerts: (json['alerts'] as List<dynamic>? ?? [])
          .map((e) => HeavyRainAlertItem.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}
