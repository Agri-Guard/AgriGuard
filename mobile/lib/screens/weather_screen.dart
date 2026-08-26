import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/weather_model.dart';
import '../services/api_service.dart';
import '../services/connectivity_service.dart';
import '../theme/app_theme.dart';
import '../widgets/app_scaffold.dart';

/// Weather / climate-risk tab: drought stress and heavy-rain flood warnings
/// per market, from backend/app/routers/weather.py. Unlike the other three
/// tabs, there is no bundled offline snapshot for weather (see
/// ApiService.droughtRisk's doc comment) — this screen shows a plain "needs
/// a live connection" state instead of pretending to have data it doesn't.
class WeatherScreen extends StatefulWidget {
  const WeatherScreen({super.key});

  @override
  State<WeatherScreen> createState() => _WeatherScreenState();
}

class _WeatherScreenState extends State<WeatherScreen> {
  bool _loading = false;
  bool _everLoaded = false;
  DroughtRiskResponse? _drought;
  HeavyRainAlertResponse? _rain;
  String? _error;
  bool? _wasOnline;

  Future<void> _refresh() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final api = context.read<ApiService>();
    try {
      final results = await Future.wait([
        api.droughtRisk(),
        api.heavyRainAlerts(),
      ]);
      if (!mounted) return;
      final drought = results[0] as DroughtRiskResponse?;
      final rain = results[1] as HeavyRainAlertResponse?;
      setState(() {
        _drought = drought;
        _rain = rain;
        _error = (drought == null && rain == null)
            ? 'Weather data needs a live connection to the AgriGuard backend — '
                'it isn\'t bundled offline. Check Settings, or try again once '
                'you\'re back online.'
            : null;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = 'Could not load weather data right now.');
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
          _everLoaded = true;
        });
      }
    }
  }

  Color _riskColor(String level) {
    switch (level.toUpperCase()) {
      case 'SEVERE':
        return AppColors.falling;
      case 'HIGH':
        return AppColors.warning;
      case 'MODERATE':
        return AppColors.accent;
      default:
        return AppColors.rising;
    }
  }

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final online = context.watch<ConnectivityService>().isOnline;
    if (_wasOnline == false && online == true) _refresh();
    _wasOnline = online;
  }

  @override
  Widget build(BuildContext context) {
    final hasData = (_drought?.markets.isNotEmpty ?? false) ||
        (_rain?.alerts.isNotEmpty ?? false);

    return AppScaffold(
      title: 'Weather',
      isLive: _everLoaded ? (_drought != null || _rain != null) : null,
      onRefresh: _loading ? null : _refresh,
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _refresh,
              child: _error != null && !hasData
                  ? ListView(
                      padding: const EdgeInsets.all(24),
                      children: [
                        const SizedBox(height: 80),
                        const Icon(Icons.cloud_off_outlined,
                            size: 40, color: AppColors.textSecondary),
                        const SizedBox(height: 12),
                        Center(
                          child: Text(
                            _error!,
                            textAlign: TextAlign.center,
                            style: Theme.of(context).textTheme.bodyMedium,
                          ),
                        ),
                      ],
                    )
                  : ListView(
                      padding: const EdgeInsets.all(16),
                      children: [
                        if (_drought != null && _drought!.markets.isNotEmpty) ...[
                          Text('Drought risk', style: Theme.of(context).textTheme.titleMedium),
                          const SizedBox(height: 4),
                          Text(
                            'Last ${_drought!.lookbackDays} days, as of ${_drought!.generatedForDate}',
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                          const SizedBox(height: 10),
                          ..._drought!.markets.map((m) => Card(
                                margin: const EdgeInsets.only(bottom: 10),
                                child: ListTile(
                                  leading: CircleAvatar(
                                    backgroundColor: _riskColor(m.riskLevel).withOpacity(0.15),
                                    child: Icon(Icons.water_drop_outlined, color: _riskColor(m.riskLevel)),
                                  ),
                                  title: Text('${m.marketName} · ${m.region}'),
                                  subtitle: Text(
                                    '${m.deficitDays}/${m.lookbackDays} days below deficit threshold'
                                    '${m.avgWaterBalanceMm != null ? ' · avg water balance ${m.avgWaterBalanceMm!.toStringAsFixed(1)} mm' : ''}',
                                  ),
                                  trailing: Text(
                                    m.riskLevel,
                                    style: TextStyle(color: _riskColor(m.riskLevel), fontWeight: FontWeight.w700),
                                  ),
                                ),
                              )),
                          const SizedBox(height: 20),
                        ],
                        if (_rain != null && _rain!.alerts.isNotEmpty) ...[
                          Text('Heavy rain / flood warnings', style: Theme.of(context).textTheme.titleMedium),
                          const SizedBox(height: 4),
                          Text(
                            'Above ${_rain!.thresholdMm.toStringAsFixed(0)} mm, last ${_rain!.lookbackDays} days',
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                          const SizedBox(height: 10),
                          ..._rain!.alerts.map((a) => Card(
                                margin: const EdgeInsets.only(bottom: 10),
                                child: ListTile(
                                  leading: const CircleAvatar(
                                    backgroundColor: Color(0x1F1976D2),
                                    child: Icon(Icons.thunderstorm_outlined, color: Color(0xFF1976D2)),
                                  ),
                                  title: Text('${a.marketName} · ${a.region}'),
                                  subtitle: Text(
                                    '${a.rainfallMm.toStringAsFixed(0)} mm on ${a.readingDate}'
                                    '${a.isForecast ? ' (forecast)' : ''}',
                                  ),
                                ),
                              )),
                        ],
                        if (!hasData)
                          Padding(
                            padding: const EdgeInsets.only(top: 60),
                            child: Center(
                              child: Text(
                                'No drought or heavy-rain risk right now.',
                                style: Theme.of(context).textTheme.bodyMedium,
                              ),
                            ),
                          ),
                      ],
                    ),
            ),
    );
  }
}
