import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'screens/forecast_screen.dart';
import 'screens/market_screen.dart';
import 'screens/alerts_screen.dart';
import 'services/api_service.dart';
import 'offline/local_cache.dart';
import 'offline/sync_service.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const AgriGuardApp());
}

class AgriGuardApp extends StatelessWidget {
  const AgriGuardApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        Provider(create: (_) => ApiService()),
        Provider(create: (_) => LocalCache()),
        ProxyProvider2<ApiService, LocalCache, SyncService>(
          update: (_, api, cache, __) => SyncService(api: api, cache: cache),
        ),
      ],
      child: MaterialApp(
        title: 'AgriGuard',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFF2E7D32),
            brightness: Brightness.light,
          ),
          useMaterial3: true,
          appBarTheme: const AppBarTheme(
            centerTitle: true,
            elevation: 0,
          ),
        ),
        home: const HomeShell(),
      ),
    );
  }
}

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  static const _pages = [
    ForecastScreen(),
    MarketScreen(),
    AlertsScreen(),
  ];

  static const _prefetchPairs = [
    ('Maize', 'Kampala'),
    ('Beans', 'Kampala'),
    ('Cassava', 'Kampala'),
  ];

  @override
  void initState() {
    super.initState();
    // Warm the offline cache in the background whenever the app opens with
    // connectivity, so ForecastScreen has something to fall back on the
    // next time a request fails (see ForecastScreen._load).
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<SyncService>().prefetch(_prefetchPairs);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(index: _index, children: _pages),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.trending_up_outlined),
            selectedIcon: Icon(Icons.trending_up),
            label: 'Forecast',
          ),
          NavigationDestination(
            icon: Icon(Icons.storefront_outlined),
            selectedIcon: Icon(Icons.storefront),
            label: 'Markets',
          ),
          NavigationDestination(
            icon: Icon(Icons.notifications_outlined),
            selectedIcon: Icon(Icons.notifications),
            label: 'Alerts',
          ),
        ],
      ),
    );
  }
}
