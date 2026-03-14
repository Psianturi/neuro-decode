import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../config/app_identity_store.dart';
import 'history_insights_screen.dart';
import '../profile/profile_memory_screen.dart';
import '../profile/profile_memory_service.dart';
import 'session_summary_service.dart';
import '../../theme/app_theme.dart';

class HomeDashboardScreen extends StatefulWidget {
  const HomeDashboardScreen({
    super.key,
    required this.cameras,
    required this.onGoSupport,
  });

  final List<CameraDescription> cameras;
  final VoidCallback onGoSupport;

  @override
  State<HomeDashboardScreen> createState() => _HomeDashboardScreenState();
}

class _HomeDashboardScreenState extends State<HomeDashboardScreen> {
  final SessionSummaryService _summaryService = SessionSummaryService();
  final AppIdentityStore _identityStore = AppIdentityStore();
  final ProfileMemoryService _profileService = ProfileMemoryService();
  SessionSummary? _latestSummary;
  ProfileRecord? _activeProfile;
  ProfileMemoryContext? _profileContext;
  bool _isLoadingSummary = false;
  bool _isLoadingProfile = false;
  bool _isCheckingProfileId = false;
  String? _activeProfileId;

  @override
  void initState() {
    super.initState();
    _refreshLatestSummary();
    _loadActiveProfileId();
  }

  Future<void> _loadActiveProfileId() async {
    final profileId = await _identityStore.getActiveProfileId();
    if (!mounted) {
      return;
    }
    setState(() {
      _activeProfileId = profileId;
    });
    if (profileId != null && profileId.isNotEmpty) {
      await _refreshProfileSummary();
    }
  }

  void _scheduleProfileIdSync() {
    if (_isCheckingProfileId) {
      return;
    }
    _isCheckingProfileId = true;
    _identityStore.getActiveProfileId().then((profileId) async {
      if (!mounted || profileId == _activeProfileId) {
        return;
      }
      setState(() {
        _activeProfileId = profileId;
      });
      if (profileId != null && profileId.isNotEmpty) {
        await _refreshProfileSummary();
      } else {
        if (!mounted) {
          return;
        }
        setState(() {
          _activeProfile = null;
          _profileContext = null;
        });
      }
    }).whenComplete(() {
      _isCheckingProfileId = false;
    });
  }

  Future<void> _refreshProfileSummary() async {
    final profileId = _activeProfileId;
    if (profileId == null || profileId.isEmpty || _isLoadingProfile) {
      return;
    }
    setState(() {
      _isLoadingProfile = true;
    });
    try {
      final results = await Future.wait<Object?>([
        _profileService.fetchProfile(profileId),
        _profileService.fetchMemoryContext(profileId),
      ]);
      if (!mounted) {
        return;
      }
      setState(() {
        _activeProfile = results[0] as ProfileRecord?;
        _profileContext = results[1] as ProfileMemoryContext;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _activeProfile = null;
        _profileContext = null;
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoadingProfile = false;
        });
      }
    }
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
    _scheduleProfileIdSync();
    return Scaffold(
      appBar: AppBar(title: const Text('NeuroDecode AI')),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Column(
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
              const SizedBox(height: 20),
              Container(
                padding: const EdgeInsets.all(18),
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
                          width: 118,
                          height: 118,
                          fit: BoxFit.cover,
                        ),
                      ),
                    ),
                    const SizedBox(height: 10),
                    Text(
                      'Hello. Wishing you a calm day.',
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Review the latest session, check insights, and open Live Support when you need real-time guidance.',
                      style: TextStyle(color: NeuroColors.textSecondary),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),
              _ProfileSummaryCard(
                profileId: _activeProfileId,
                profile: _activeProfile,
                contextSummary: _profileContext,
                isLoading: _isLoadingProfile,
                onOpen: _activeProfileId == null || _activeProfileId!.isEmpty
                    ? null
                    : () async {
                        await Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => ProfileMemoryScreen(
                              profileId: _activeProfileId!,
                            ),
                          ),
                        );
                        await _refreshProfileSummary();
                      },
                onGoSupport: widget.onGoSupport,
              ),
              const SizedBox(height: 12),
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
                        builder: (_) =>
                            HistoryInsightsScreen(service: _summaryService),
                      ),
                    );
                    await _refreshLatestSummary();
                  },
                  icon: const Icon(Icons.history),
                  label: const Text('VIEW HISTORY / INSIGHTS'),
                ),
              ),
              const SizedBox(height: 16),
              SizedBox(
                height: 46,
                child: OutlinedButton.icon(
                  onPressed: widget.onGoSupport,
                  icon: const Icon(Icons.support_agent),
                  label: const Text('GO TO LIVE SUPPORT'),
                ),
              ),
            ],
          ),
        ],
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
              Expanded(
                child: Text(
                  'Latest Session Summary',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
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
              'No completed session yet. Run live support and return to dashboard.',
              style: TextStyle(color: NeuroColors.textSecondary),
            ),
          ] else ...[
            Text(
              summary!.title,
              style: Theme.of(context).textTheme.titleSmall,
            ),
            const SizedBox(height: 4),
            Text(
              'Duration ${summary!.durationMinutes} min • ${_formatUtc(summary!.timestampUtc)}',
              style: const TextStyle(color: NeuroColors.textSecondary),
            ),
            const SizedBox(height: 12),
            _InsightRow(
              icon: Icons.visibility,
              label: 'Visual Trigger',
              text: summary!.triggersVisual,
            ),
            const SizedBox(height: 8),
            _InsightRow(
              icon: Icons.hearing,
              label: 'Audio Trigger',
              text: summary!.triggersAudio,
            ),
            const SizedBox(height: 8),
            _InsightRow(
              icon: Icons.psychology_alt,
              label: 'Agent Action',
              text: summary!.agentActions,
            ),
            const SizedBox(height: 8),
            _InsightRow(
              icon: Icons.lightbulb,
              label: 'Follow-up',
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

class _ProfileSummaryCard extends StatelessWidget {
  const _ProfileSummaryCard({
    required this.profileId,
    required this.profile,
    required this.contextSummary,
    required this.isLoading,
    required this.onOpen,
    required this.onGoSupport,
  });

  final String? profileId;
  final ProfileRecord? profile;
  final ProfileMemoryContext? contextSummary;
  final bool isLoading;
  final VoidCallback? onOpen;
  final VoidCallback onGoSupport;

  @override
  Widget build(BuildContext context) {
    final hasProfile = profileId != null && profileId!.isNotEmpty;
    final title = profile?.name.isNotEmpty == true
        ? profile!.name
        : hasProfile
            ? profileId!
            : 'No support profile selected';

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
              const Icon(Icons.badge_outlined, color: NeuroColors.primary),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Active Profile Summary',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
              if (isLoading)
                const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
            ],
          ),
          const SizedBox(height: 10),
          Text(title, style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: 6),
          if (!hasProfile)
            const Text(
              'Set a profile in Support to help Buddy remember who is being supported and what usually helps.',
              style: TextStyle(color: NeuroColors.textSecondary),
            )
          else ...[
            Text(
              profile?.notes.isNotEmpty == true
                  ? profile!.notes
                  : 'Profile is active. Add a short support summary and a few memory notes to make later sessions more personalized.',
              style: const TextStyle(color: NeuroColors.textSecondary),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _ProfileChip(
                  label: 'Memory notes',
                  value: '${contextSummary?.memoryItemCount ?? 0}',
                ),
                _ProfileChip(
                  label: 'Recent sessions',
                  value: '${contextSummary?.recentSessionCount ?? 0}',
                ),
                if (profile?.childName.isNotEmpty == true)
                  _ProfileChip(label: 'Child', value: profile!.childName),
                if (profile?.caregiverName.isNotEmpty == true)
                  _ProfileChip(
                    label: 'Caregiver',
                    value: profile!.caregiverName,
                  ),
              ],
            ),
          ],
          const SizedBox(height: 12),
          SizedBox(
            height: 46,
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: hasProfile ? onOpen : onGoSupport,
              icon: const Icon(Icons.psychology_alt_outlined),
              label: Text(
                hasProfile
                    ? 'OPEN PROFILE WORKSPACE'
                    : 'SET PROFILE IN SUPPORT',
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ProfileChip extends StatelessWidget {
  const _ProfileChip({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: NeuroColors.surfaceVariant,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Text(
        '$label: $value',
        style: const TextStyle(
          color: NeuroColors.textPrimary,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
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
