import 'package:flutter/material.dart';

/// Small app-bar chip showing whether the data on screen came from the
/// live backend or the bundled offline snapshot. Every screen that calls
/// ApiService should show this — silently falling back to stale bundled
/// data with no indication was the original bug report.
class DataSourceChip extends StatelessWidget {
  final bool isLive;

  const DataSourceChip({super.key, required this.isLive});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: Chip(
        visualDensity: VisualDensity.compact,
        avatar: Icon(
          isLive ? Icons.cloud_done : Icons.cloud_off,
          size: 16,
          color: isLive ? Colors.green.shade700 : Colors.orange.shade800,
        ),
        label: Text(isLive ? 'Live' : 'Offline'),
      ),
    );
  }
}
