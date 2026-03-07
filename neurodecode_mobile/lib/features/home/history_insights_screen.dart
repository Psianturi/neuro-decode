import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../theme/app_theme.dart';
import 'session_summary_service.dart';

class HistoryInsightsScreen extends StatefulWidget {
  const HistoryInsightsScreen({
    super.key,
    required this.service,
  });

  final SessionSummaryService service;

  @override
  State<HistoryInsightsScreen> createState() => _HistoryInsightsScreenState();
}

class _HistoryInsightsScreenState extends State<HistoryInsightsScreen> {
  bool _isLoading = false;
  String? _error;
  List<SessionSummary> _items = const <SessionSummary>[];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (_isLoading) {
      return;
    }

    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final data = await widget.service.fetchAll();
      if (!mounted) {
        return;
      }
      setState(() {
        _items = data;
      });
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = e.toString();
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('History / Insights')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16),
          children: [
            if (_isLoading && _items.isEmpty)
              const Padding(
                padding: EdgeInsets.only(top: 64),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (_error != null && _items.isEmpty)
              _StateMessageCard(
                icon: Icons.cloud_off,
                title: 'Gagal memuat history',
                subtitle: _error!,
                onAction: _load,
                actionLabel: 'Coba lagi',
              )
            else if (_items.isEmpty)
              _StateMessageCard(
                icon: Icons.history_toggle_off,
                title: 'Belum ada riwayat sesi',
                subtitle:
                    'Selesaikan sesi live support terlebih dahulu untuk melihat insight di sini.',
                onAction: _load,
                actionLabel: 'Refresh',
              )
            else ...[
              Text(
                '10 sesi terakhir',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 6),
              const Text(
                'Gunakan data ini untuk melihat pola trigger dan tindak lanjut dari waktu ke waktu.',
                style: TextStyle(color: NeuroColors.textSecondary),
              ),
              const SizedBox(height: 12),
              for (final item in _items) _SessionCard(summary: item),
            ],
          ],
        ),
      ),
    );
  }
}

class _SessionCard extends StatelessWidget {
  const _SessionCard({required this.summary});

  final SessionSummary summary;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          tilePadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 2),
          childrenPadding: const EdgeInsets.fromLTRB(14, 0, 14, 14),
          title: Text(
            summary.title,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
          subtitle: Text(
            '${_formatTime(summary.timestampUtc)} • ${summary.durationMinutes} menit • ${summary.closeReason}',
            style: const TextStyle(color: NeuroColors.textSecondary),
          ),
          leading: const Icon(Icons.event_note, color: NeuroColors.primary),
          children: [
            _DetailRow(
              icon: Icons.visibility,
              label: 'Pemicu Visual',
              text: summary.triggersVisual,
            ),
            const SizedBox(height: 8),
            _DetailRow(
              icon: Icons.hearing,
              label: 'Pemicu Audio',
              text: summary.triggersAudio,
            ),
            const SizedBox(height: 8),
            _DetailRow(
              icon: Icons.psychology_alt,
              label: 'Tindakan Agen',
              text: summary.agentActions,
            ),
            const SizedBox(height: 8),
            _DetailRow(
              icon: Icons.lightbulb,
              label: 'Tindak Lanjut',
              text: summary.followUp,
            ),
            const SizedBox(height: 8),
            _DetailRow(
              icon: Icons.health_and_safety,
              label: 'Safety Note',
              text: summary.safetyNote,
            ),
          ],
        ),
      ),
    );
  }

  static String _formatTime(String raw) {
    try {
      return DateFormat('dd MMM yyyy • HH:mm').format(
        DateTime.parse(raw).toLocal(),
      );
    } catch (_) {
      return raw;
    }
  }
}

class _DetailRow extends StatelessWidget {
  const _DetailRow({
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

class _StateMessageCard extends StatelessWidget {
  const _StateMessageCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onAction,
    required this.actionLabel,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final Future<void> Function() onAction;
  final String actionLabel;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: NeuroColors.surface,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: [
          Icon(icon, color: NeuroColors.primary, size: 32),
          const SizedBox(height: 10),
          Text(
            title,
            style: Theme.of(context).textTheme.titleMedium,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 6),
          Text(
            subtitle,
            style: const TextStyle(color: NeuroColors.textSecondary),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 14),
          OutlinedButton(
            onPressed: onAction,
            child: Text(actionLabel),
          ),
        ],
      ),
    );
  }
}
