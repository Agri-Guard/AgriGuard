import 'package:flutter/material.dart';
import '../models/forecast_model.dart';

/// Compact card showing a single forecast horizon summary or a key metric.
class ForecastCard extends StatelessWidget {
  final ForecastResponse forecast;
  final VoidCallback? onTap;

  const ForecastCard({
    super.key,
    required this.forecast,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isUp = forecast.pctChange >= 0;
    final trendColor = isUp ? Colors.green.shade700 : Colors.red.shade700;
    final trendIcon = isUp ? Icons.trending_up : Icons.trending_down;

    return Card(
      elevation: 2,
      margin: const EdgeInsets.symmetric(vertical: 6),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      '${forecast.commodity} · ${forecast.market}',
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                  Icon(trendIcon, color: trendColor, size: 22),
                  const SizedBox(width: 4),
                  Text(
                    '${isUp ? '+' : ''}${forecast.pctChange.toStringAsFixed(1)}%',
                    style: TextStyle(
                      color: trendColor,
                      fontWeight: FontWeight.bold,
                      fontSize: 15,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                'Horizon: ${forecast.horizonDays} days · Model: ${forecast.modelUsed}',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 12),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  _metric(
                    context,
                    'Last predicted',
                    '${forecast.lastPredicted.toStringAsFixed(0)} ${forecast.currency}/${forecast.unit}',
                  ),
                  _metric(
                    context,
                    'Trend',
                    forecast.trend,
                  ),
                  _metric(
                    context,
                    'Obs used',
                    '${forecast.observationsUsed}',
                  ),
                ],
              ),
              if (forecast.alert != null && forecast.alert!.isNotEmpty) ...[
                const SizedBox(height: 12),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                  decoration: BoxDecoration(
                    color: theme.colorScheme.errorContainer.withOpacity(0.4),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        Icons.warning_amber_rounded,
                        size: 18,
                        color: theme.colorScheme.error,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          forecast.alert!,
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.onErrorContainer,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _metric(BuildContext context, String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: Theme.of(context).textTheme.labelSmall?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
        ),
        const SizedBox(height: 2),
        Text(
          value,
          style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
        ),
      ],
    );
  }
}

/// Small tile for an individual forecast point (used in the detail list).
class ForecastPointTile extends StatelessWidget {
  final ForecastPoint point;
  final String currency;
  final String unit;

  const ForecastPointTile({
    super.key,
    required this.point,
    this.currency = 'UGX',
    this.unit = 'KG',
  });

  @override
  Widget build(BuildContext context) {
    return ListTile(
      dense: true,
      title: Text(point.date),
      subtitle: Text(
        'Range ${point.lowerBound.toStringAsFixed(0)} – ${point.upperBound.toStringAsFixed(0)}',
      ),
      trailing: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Text(
            '${point.predictedPrice.toStringAsFixed(0)} $currency',
            style: const TextStyle(fontWeight: FontWeight.w600),
          ),
          Text(
            '${(point.confidence * 100).toStringAsFixed(0)}% conf',
            style: Theme.of(context).textTheme.labelSmall,
          ),
        ],
      ),
    );
  }
}