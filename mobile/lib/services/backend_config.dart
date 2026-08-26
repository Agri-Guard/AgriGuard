import 'package:shared_preferences/shared_preferences.dart';

/// Where the app looks for the live AgriGuard backend.
///
/// IMPORTANT — intellectual-property note:
/// Earlier builds exposed a raw "Backend URL" text field (with emulator
/// aliases, LAN-IP instructions, etc.) directly in Settings. That leaks
/// infrastructure details — hostnames, ports, hosting provider — to anyone
/// who opens the app, which is unnecessary and gives away information about
/// how AgriGuard is deployed for free. None of that belongs in a
/// production build, so it has been removed from the UI entirely.
///
/// What ships now:
///   1. [productionBaseUrl] — a single baked-in constant. Fill this in once
///      you deploy the FastAPI backend (Render / Railway / Fly.io / your own
///      server) and rebuild. Every user gets live data automatically; no
///      one ever sees or edits this value.
///   2. A hidden developer override, reachable only by tapping the version
///      number in Settings → About seven times (the same pattern Android
///      itself uses for "Developer options"). This is for your own
///      on-device testing against a local server and is not documented or
///      discoverable anywhere in the normal UI.
///
/// If neither is set/reachable, [ApiService] silently serves the bundled
/// offline snapshot — the app always works, it just isn't live.
class BackendConfig {
  BackendConfig._();

  /// Fill this in once the backend is deployed, e.g.
  /// 'https://agriguard-api.onrender.com'. Leave empty during development —
  /// the app will run entirely on the bundled offline data plus whatever
  /// you set via the hidden developer override below.
  static const String productionBaseUrl = '';

  static const _devOverrideKey = 'agriguard_dev_backend_override';
  static String? _cachedOverride;

  static Future<String> getBaseUrl() async {
    final override = await _getDevOverride();
    if (override != null && override.isNotEmpty) return override;
    return productionBaseUrl;
  }

  static Future<String?> _getDevOverride() async {
    if (_cachedOverride != null) return _cachedOverride;
    final prefs = await SharedPreferences.getInstance();
    _cachedOverride = prefs.getString(_devOverrideKey) ?? '';
    return _cachedOverride;
  }

  /// Developer-only: set a local override (e.g. `http://10.0.2.2:8000` for
  /// the Android emulator, or your dev machine's LAN IP). Reached only via
  /// the hidden long-tap gesture in Settings — never surfaced as a normal
  /// setting.
  static Future<void> setDevOverride(String url) async {
    final trimmed = url.trim().replaceAll(RegExp(r'/+$'), '');
    final prefs = await SharedPreferences.getInstance();
    if (trimmed.isEmpty) {
      await prefs.remove(_devOverrideKey);
    } else {
      await prefs.setString(_devOverrideKey, trimmed);
    }
    _cachedOverride = trimmed;
  }

  static Future<bool> hasDevOverride() async {
    final v = await _getDevOverride();
    return v != null && v.isNotEmpty;
  }
}
