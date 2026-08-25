import 'package:shared_preferences/shared_preferences.dart';

/// Where the app looks for a live AgriGuard backend, persisted across
/// launches. Same idea as the "Backend URL" field on the desktop dashboard
/// (default `http://localhost:8000`) — except a phone is never on the same
/// machine as the FastAPI process, so there is no safe default to ship here.
///
/// Empty means "no backend configured": [ApiService] skips the network
/// entirely and serves the bundled offline snapshot, instead of burning a
/// timeout on every screen load.
class BackendConfig {
  static const _key = 'agriguard_backend_url';
  static String? _cached;

  /// Common presets shown in the Settings screen. `10.0.2.2` is the Android
  /// emulator's alias for the host machine's `localhost`; a real phone needs
  /// either the dev machine's LAN IP (see network_security_config.xml) or a
  /// publicly reachable HTTPS URL (e.g. the backend deployed to Render /
  /// Railway / Fly.io) to work off Keith's Wi-Fi.
  static const presets = <String, String>{
    'Android emulator (this machine)': 'http://10.0.2.2:8000',
    'Not configured (offline only)': '',
  };

  static Future<String> getBaseUrl() async {
    if (_cached != null) return _cached!;
    final prefs = await SharedPreferences.getInstance();
    _cached = prefs.getString(_key) ?? '';
    return _cached!;
  }

  static Future<void> setBaseUrl(String url) async {
    final trimmed = url.trim().replaceAll(RegExp(r'/+$'), ''); // no trailing slash
    final prefs = await SharedPreferences.getInstance();
    if (trimmed.isEmpty) {
      await prefs.remove(_key);
    } else {
      await prefs.setString(_key, trimmed);
    }
    _cached = trimmed;
  }
}
