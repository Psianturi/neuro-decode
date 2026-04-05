import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../config/app_identity_store.dart';
import '../profile/profile_memory_service.dart';
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
  final AppIdentityStore _identityStore = AppIdentityStore();
  final ProfileMemoryService _profileMemoryService = ProfileMemoryService();
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

  Future<void> _saveSuggestedMemory({
    required String category,
    required String note,
  }) async {
    final profileId = await _identityStore.getActiveProfileId();
    if (profileId == null || profileId.isEmpty) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content:
              Text('Set an active profile in Support before saving memory.'),
        ),
      );
      return;
    }

    try {
      await _profileMemoryService.addMemory(
        profileId: profileId,
        category: category,
        note: note,
        confidence: 'medium',
      );
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Saved to profile memory: $profileId')),
      );
    } catch (e) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to save memory: $e')),
      );
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
                title: 'Unable to load history',
                subtitle: _error!,
                onAction: _load,
                actionLabel: 'Try again',
              )
            else if (_items.isEmpty)
              _StateMessageCard(
                icon: Icons.history_toggle_off,
                title: 'No session history yet',
                subtitle:
                    'Complete a live support session first to see insights here.',
                onAction: _load,
                actionLabel: 'Refresh',
              )
            else ...[
              Text(
                'Recent sessions',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 6),
              const Text(
                'Use these summaries to review trigger patterns and follow-up actions over time.',
                style: TextStyle(color: NeuroColors.textSecondary),
              ),
              const SizedBox(height: 12),
              for (final item in _items)
                _SessionCard(
                  summary: item,
                  onSaveSuggestion: _saveSuggestedMemory,
                  service: widget.service,
                ),
            ],
          ],
        ),
      ),
    );
  }
}

class _SessionCard extends StatefulWidget {
  const _SessionCard({
    required this.summary,
    required this.onSaveSuggestion,
    required this.service,
  });

  final SessionSummary summary;
  final Future<void> Function({required String category, required String note})
      onSaveSuggestion;
  final SessionSummaryService service;

  @override
  State<_SessionCard> createState() => _SessionCardState();
}

class _SessionCardState extends State<_SessionCard> {
  late int? _rating;
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    _rating = widget.summary.caregiverRating;
  }

  Future<void> _submitRating(int stars) async {
    if (_submitting || widget.summary.sessionId.isEmpty) return;
    setState(() {
      _submitting = true;
      _rating = stars;
    });
    try {
      await widget.service.rateSession(widget.summary.sessionId, stars);
    } catch (_) {
      // Best-effort — local state already updated optimistically.
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

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
            widget.summary.title,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
          subtitle: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '${_formatTime(widget.summary.timestampUtc)} • ${widget.summary.durationMinutes} min • ${widget.summary.closeReasonLabel}',
                style: const TextStyle(color: NeuroColors.textSecondary),
              ),
              if (widget.summary.memoryAssisted)
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: NeuroColors.surfaceVariant,
                      borderRadius: BorderRadius.circular(999),
                      border: Border.all(color: NeuroColors.primary),
                    ),
                    child: Text(
                      widget.summary.memoryProfileId.isEmpty
                          ? 'Memory Assisted'
                          : 'Memory Assisted • ${widget.summary.memoryProfileId}',
                      style: const TextStyle(
                        color: NeuroColors.primary,
                        fontWeight: FontWeight.w700,
                        fontSize: 12,
                      ),
                    ),
                  ),
                ),
            ],
          ),
          leading: const Icon(Icons.event_note, color: NeuroColors.primary),
          children: [
            _DetailRow(
              icon: Icons.visibility,
              label: 'Visual Trigger',
              text: widget.summary.triggersVisual,
            ),
            const SizedBox(height: 8),
            _DetailRow(
              icon: Icons.hearing,
              label: 'Audio Trigger',
              text: widget.summary.triggersAudio,
            ),
            const SizedBox(height: 8),
            _DetailRow(
              icon: Icons.psychology_alt,
              label: 'Agent Action',
              text: widget.summary.agentActions,
            ),
            const SizedBox(height: 8),
            _DetailRow(
              icon: Icons.lightbulb,
              label: 'Follow-up',
              text: widget.summary.followUp,
            ),
            const SizedBox(height: 8),
            _DetailRow(
              icon: Icons.health_and_safety,
              label: 'Safety Note',
              text: widget.summary.safetyNote,
            ),
            const SizedBox(height: 12),
            // Star rating row
            Row(
              children: [
                const Text(
                  'Rate this session:',
                  style: TextStyle(
                    fontSize: 13,
                    color: NeuroColors.textSecondary,
                  ),
                ),
                const SizedBox(width: 8),
                for (int star = 1; star <= 5; star++)
                  GestureDetector(
                    onTap: _submitting ? null : () => _submitRating(star),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 2),
                      child: Icon(
                        (_rating != null && star <= _rating!)
                            ? Icons.star
                            : Icons.star_border,
                        size: 26,
                        color: (_rating != null && star <= _rating!)
                            ? Colors.amber
                            : NeuroColors.textSecondary,
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                if (widget.summary.triggersAudio != '-')
                  OutlinedButton.icon(
                    onPressed: () => widget.onSaveSuggestion(
                      category: 'trigger',
                      note: 'Audio trigger pattern: ${widget.summary.triggersAudio}',
                    ),
                    icon: const Icon(Icons.hearing, size: 18),
                    label: const Text('Save audio trigger'),
                  ),
                if (widget.summary.triggersVisual != '-')
                  OutlinedButton.icon(
                    onPressed: () => widget.onSaveSuggestion(
                      category: 'trigger',
                      note: 'Visual trigger pattern: ${widget.summary.triggersVisual}',
                    ),
                    icon: const Icon(Icons.visibility, size: 18),
                    label: const Text('Save visual trigger'),
                  ),
                if (widget.summary.followUp != '-')
                  OutlinedButton.icon(
                    onPressed: () => widget.onSaveSuggestion(
                      category: 'routine',
                      note: 'Follow-up guidance: ${widget.summary.followUp}',
                    ),
                    icon: const Icon(Icons.lightbulb, size: 18),
                    label: const Text('Save follow-up'),
                  ),
              ],
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
