# AgriGuard Mobile (Flutter)

Cross-platform client for Ugandan farmers: crop price forecasts, market intelligence, and price alerts.

## Features

- **Forecast** — 7/14/28-day price forecasts for any commodity × market, with history + forecast chart (fl_chart)
- **Markets** — cross-market summary (best/worst price, national average)
- **Alerts** — watchlist of commodities with significant predicted moves or server-side alerts
- **Offline** — LocalCache + SyncService (shared_preferences + connectivity_plus)

## Prerequisites

- Flutter 3.22+ / Dart 3.3+
- Running AgriGuard FastAPI backend (default `http://10.0.2.2:8000` for Android emulator)

## Run

```bash
cd mobile
flutter pub get
flutter run
```

Edit `ApiService.baseUrl` in `lib/services/api_service.dart` for physical devices (use your machine LAN IP).

## Layout

```
lib/
  main.dart
  models/forecast_model.dart
  services/api_service.dart
  screens/{forecast,market,alerts}_screen.dart
  widgets/forecast_card.dart
  offline/{local_cache,sync_service}.dart
```

## Platform folders

`android/` and `ios/` currently contain only `.gitkeep`. To generate full native projects:

```bash
flutter create . --project-name agriguard_mobile --org ug.agriguard
```
