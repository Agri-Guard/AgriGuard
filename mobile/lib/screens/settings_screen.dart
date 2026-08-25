import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/backend_config.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _urlCtrl = TextEditingController();
  bool _testing = false;
  bool? _lastTestOk;
  String? _savedUrl;

  @override
  void initState() {
    super.initState();
    BackendConfig.getBaseUrl().then((url) {
      setState(() {
        _urlCtrl.text = url;
        _savedUrl = url;
      });
    });
  }

  @override
  void dispose() {
    _urlCtrl.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    await BackendConfig.setBaseUrl(_urlCtrl.text);
    setState(() {
      _savedUrl = _urlCtrl.text.trim();
      _lastTestOk = null;
    });
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          _savedUrl!.isEmpty
              ? 'Cleared — running on bundled offline data only.'
              : 'Saved. AgriGuard will use $_savedUrl for live prices.',
        ),
      ),
    );
  }

  Future<void> _test() async {
    await _save();
    setState(() => _testing = true);
    final ok = await context.read<ApiService>().health();
    setState(() {
      _testing = false;
      _lastTestOk = ok;
    });
  }

  @override
  Widget build(BuildContext context) {
    final isConfigured = _savedUrl != null && _savedUrl!.isNotEmpty;
    return Scaffold(
      appBar: AppBar(title: const Text('⚙️ Settings')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            color: isConfigured
                ? Colors.green.withOpacity(0.08)
                : Colors.orange.withOpacity(0.1),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  Icon(
                    isConfigured ? Icons.cloud_done_outlined : Icons.cloud_off_outlined,
                    color: isConfigured ? Colors.green.shade700 : Colors.orange.shade800,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      isConfigured
                          ? 'Live backend configured — prices refresh from the server.'
                          : 'No backend configured — AgriGuard is showing a bundled, '
                              'point-in-time snapshot until you set one below.',
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 20),
          Text('Backend URL', style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: 8),
          TextField(
            controller: _urlCtrl,
            decoration: const InputDecoration(
              border: OutlineInputBorder(),
              hintText: 'https://your-agriguard-backend.example.com',
            ),
            keyboardType: TextInputType.url,
            autocorrect: false,
          ),
          const SizedBox(height: 8),
          Text(
            'Your phone can\'t reach "localhost" — that always means the '
            'phone itself. For the real AgriGuard backend, use either your '
            'dev machine\'s LAN IP (same Wi-Fi only, e.g. http://192.168.1.42:8000 — '
            'must also be added to network_security_config.xml) or a '
            'publicly deployed HTTPS URL.',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: BackendConfig.presets.entries
                .map(
                  (e) => ActionChip(
                    label: Text(e.key),
                    onPressed: () => setState(() => _urlCtrl.text = e.value),
                  ),
                )
                .toList(),
          ),
          const SizedBox(height: 20),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: _save,
                  child: const Text('Save'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: FilledButton(
                  onPressed: _testing ? null : _test,
                  child: Text(_testing ? 'Testing…' : 'Save & Test Connection'),
                ),
              ),
            ],
          ),
          if (_lastTestOk != null) ...[
            const SizedBox(height: 16),
            Row(
              children: [
                Icon(
                  _lastTestOk! ? Icons.check_circle : Icons.error_outline,
                  color: _lastTestOk! ? Colors.green.shade700 : Colors.red.shade700,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _lastTestOk!
                        ? 'Backend reachable — /health responded OK.'
                        : 'Could not reach that backend. Falling back to '
                            'offline data until it\'s reachable.',
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}
