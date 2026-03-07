import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../live_agent/live_agent_screen.dart';
import 'history_insights_screen.dart';
import 'session_summary_service.dart';
import '../../theme/app_theme.dart';

class HomeDashboardScreen extends StatefulWidget {
  const HomeDashboardScreen({
    super.key,
    required this.cameras,
  });

  final List<CameraDescription> cameras;

  @override
  State<HomeDashboardScreen> createState() => _HomeDashboardScreenState();
}

class _HomeDashboardScreenState extends State<HomeDashboardScreen> {
  bool _observerEnabled = true;
  final SessionSummaryService _summaryService = SessionSummaryService();
  SessionSummary? _latestSummary;
  bool _isLoadingSummary = false;

  @override
  void initState() {
    super.initState();
    _refreshLatestSummary();
  }

  Future<void> _refreshLatestSummary() async {
    if (_isLoadingSummary) {
      return;
    }

    setState(() {
      _isLoadingSummary = true;
    });

    try {
      final summary = await _summaryService.fetchLatest();
      if (!mounted) {
        return;
      }
      setState(() {
        _latestSummary = summary;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _latestSummary = null;
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoadingSummary = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('NeuroDecode AI')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                const _ConnectionDot(),
                const SizedBox(width: 10),
                Text(
                  'Cloud Run Connected',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
              ],
            ),
            const SizedBox(height: 32),
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: NeuroColors.surface,
                borderRadius: BorderRadius.circular(20),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Center(
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(18),
                      child: Image.asset(
                        'assets/mascot01.png',
                        width: 170,
                        height: 170,
                        fit: BoxFit.cover,
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'NeuroDecode Live Support',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Real-time decision support for caregivers. Non-medical support only.',
                    style: TextStyle(color: NeuroColors.textSecondary),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),
            Container(
              decoration: BoxDecoration(
                color: NeuroColors.surface,
                borderRadius: BorderRadius.circular(18),
              ),
              child: SwitchListTile.adaptive(
                value: _observerEnabled,
                title: const Text('Camera Observer'),
                subtitle: const Text('Enable mini camera preview in live session'),
                onChanged: (value) {
                  setState(() {
                    _observerEnabled = value;
                  });
                },
              ),
            ),
            const SizedBox(height: 16),
            _LatestSessionCard(
              summary: _latestSummary,
              isLoading: _isLoadingSummary,
              onRefresh: _refreshLatestSummary,
            ),
            const SizedBox(height: 12),
            SizedBox(
              height: 46,
              child: OutlinedButton.icon(
                onPressed: () async {
                  await Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => HistoryInsightsScreen(service: _summaryService),
                    ),
                  );
                  await _refreshLatestSummary();
                },
                icon: const Icon(Icons.history),
                label: const Text('VIEW HISTORY / INSIGHTS'),
              ),
            ),
            const Spacer(),
            SizedBox(
              height: 56,
              child: ElevatedButton.icon(
                onPressed: () async {
                  await Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => LiveAgentScreen(
                        cameras: widget.cameras,
                        observerEnabled: _observerEnabled,
                      ),
                    ),
                  );
                  await _refreshLatestSummary();
                },
                icon: const Icon(Icons.play_circle_fill),
                label: const Text('START LIVE SUPPORT'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _LatestSessionCard extends StatelessWidget {
  const _LatestSessionCard({
    required this.summary,
    required this.isLoading,
    required this.onRefresh,
  });

  final SessionSummary? summary;
  final bool isLoading;
  final Future<void> Function() onRefresh;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: NeuroColors.surface,
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.history_edu, color: NeuroColors.primary),
              const SizedBox(width: 8),
              Text(
                'Ringkasan Sesi Terakhir',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const Spacer(),
              IconButton(
                onPressed: isLoading ? null : onRefresh,
                icon: isLoading
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.refresh),
                tooltip: 'Refresh summary',
              ),
            ],
          ),
          const SizedBox(height: 8),
          if (summary == null) ...[
            const Text(
              'Belum ada sesi yang selesai. Jalankan live support lalu kembali ke dashboard.',
              style: TextStyle(color: NeuroColors.textSecondary),
            ),
          ] else ...[
            Text(
              summary!.title,
              style: Theme.of(context).textTheme.titleSmall,
            ),
            const SizedBox(height: 4),
            Text(
              'Durasi ${summary!.durationMinutes} menit • ${_formatUtc(summary!.timestampUtc)}',
              style: const TextStyle(color: NeuroColors.textSecondary),
            ),
            const SizedBox(height: 12),
            _InsightRow(
              icon: Icons.visibility,
              label: 'Pemicu Visual',
              text: summary!.triggersVisual,
            ),
            const SizedBox(height: 8),
            _InsightRow(
              icon: Icons.hearing,
              label: 'Pemicu Audio',
              text: summary!.triggersAudio,
            ),
            const SizedBox(height: 8),
            _InsightRow(
              icon: Icons.psychology_alt,
              label: 'Tindakan Agen',
              text: summary!.agentActions,
            ),
            const SizedBox(height: 8),
            _InsightRow(
              icon: Icons.lightbulb,
              label: 'Tindak Lanjut',
              text: summary!.followUp,
            ),
          ],
        ],
      ),
    );
  }

  static String _formatUtc(String raw) {
    try {
      final dt = DateTime.parse(raw).toLocal();
      return DateFormat('dd MMM HH:mm').format(dt);
    } catch (_) {
      return raw;
    }
  }
}

class _InsightRow extends StatelessWidget {
  const _InsightRow({
    required this.icon,
    required this.label,
    required this.text,
  });

  final IconData icon;
  final String label;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 18, color: NeuroColors.primary),
        const SizedBox(width: 8),
        Expanded(
          child: RichText(
            text: TextSpan(
              style: DefaultTextStyle.of(context).style,
              children: [
                TextSpan(
                  text: '$label: ',
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
                TextSpan(text: text),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _ConnectionDot extends StatefulWidget {
  const _ConnectionDot();

  @override
  State<_ConnectionDot> createState() => _ConnectionDotState();
}

class _ConnectionDotState extends State<_ConnectionDot>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
      lowerBound: 0.3,
      upperBound: 1,
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _controller,
      child: Container(
        width: 10,
        height: 10,
        decoration: const BoxDecoration(
          shape: BoxShape.circle,
          color: NeuroColors.primary,
        ),
      ),
    );
  }
}
