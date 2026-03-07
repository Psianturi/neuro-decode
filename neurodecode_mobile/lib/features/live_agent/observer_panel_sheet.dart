import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../theme/app_theme.dart';

enum ObserverConfidence { low, medium, high }

class ObserverEvent {
  const ObserverEvent({
    required this.timestamp,
    required this.text,
    required this.confidence,
  });

  final DateTime timestamp;
  final String text;
  final ObserverConfidence confidence;
}

class ObserverPanelSheet extends StatelessWidget {
  const ObserverPanelSheet({
    super.key,
    required this.events,
  });

  final List<ObserverEvent> events;

  @override
  Widget build(BuildContext context) {
    final latestConfidence =
        events.isNotEmpty ? events.last.confidence : ObserverConfidence.low;

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 44,
                height: 4,
                decoration: BoxDecoration(
                  color: Colors.white24,
                  borderRadius: BorderRadius.circular(20),
                ),
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                const Icon(Icons.visibility, color: NeuroColors.primary),
                const SizedBox(width: 8),
                Text(
                  'Observer Panel',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const Spacer(),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              'Confidence Meter',
              style: Theme.of(context).textTheme.titleSmall,
            ),
            const SizedBox(height: 8),
            _ConfidenceBar(confidence: latestConfidence),
            const SizedBox(height: 16),
            Text(
              'Behavior Timeline',
              style: Theme.of(context).textTheme.titleSmall,
            ),
            const SizedBox(height: 8),
            Expanded(
              child: events.isEmpty
                  ? const Center(
                      child: Text(
                        'No observer events yet.',
                        style: TextStyle(color: Colors.white60),
                      ),
                    )
                  : ListView.separated(
                      itemCount: events.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 8),
                      itemBuilder: (context, index) {
                        final event = events[events.length - 1 - index];
                        final time = DateFormat('HH:mm:ss').format(event.timestamp);
                        return Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: NeuroColors.surface,
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                '[$time] ${event.confidence.name.toUpperCase()}',
                                style: const TextStyle(
                                  fontSize: 12,
                                  color: Colors.white70,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(event.text),
                            ],
                          ),
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ConfidenceBar extends StatelessWidget {
  const _ConfidenceBar({required this.confidence});

  final ObserverConfidence confidence;

  @override
  Widget build(BuildContext context) {
    final value = switch (confidence) {
      ObserverConfidence.low => 0.33,
      ObserverConfidence.medium => 0.66,
      ObserverConfidence.high => 1.0,
    };

    final color = switch (confidence) {
      ObserverConfidence.low => Colors.greenAccent,
      ObserverConfidence.medium => NeuroColors.secondary,
      ObserverConfidence.high => Colors.redAccent,
    };

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(8),
          child: LinearProgressIndicator(
            value: value,
            minHeight: 12,
            backgroundColor: Colors.white12,
            valueColor: AlwaysStoppedAnimation<Color>(color),
          ),
        ),
        const SizedBox(height: 6),
        Text('Current: ${confidence.name.toUpperCase()}'),
      ],
    );
  }
}
