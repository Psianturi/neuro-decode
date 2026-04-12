import 'dart:async';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../config/app_identity_store.dart';
import 'history_insights_screen.dart';
import 'notification_service.dart';
import 'notifications_center_screen.dart';
import 'push_registration_service.dart';
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
  final NotificationService _notificationService = NotificationService();
  final PushRegistrationService _pushRegistrationService =
      PushRegistrationService();
  final AppIdentityStore _identityStore = AppIdentityStore();
  final ProfileMemoryService _profileService = ProfileMemoryService();
  SessionSummary? _latestSummary;
  ProfileRecord? _activeProfile;
  ProfileMemoryContext? _profileContext;
  bool _isLoadingSummary = false;
  bool _isLoadingNotifications = false;
  bool _isCheckingUnreadSync = false;
  bool _isLoadingProfile = false;
  bool _isCheckingProfileId = false;
  bool _isSyncingPushToken = false;
  String? _activeProfileId;
  int _unreadNotificationCount = 0;
  DateTime? _lastUnreadSyncAt;

  @override
  void initState() {
    super.initState();
    _refreshLatestSummary();
    _refreshUnreadNotifications();
    _loadActiveProfileId();
    _syncPushToken();
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
    await _syncPushToken();
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
      await _syncPushToken();
    }).whenComplete(() {
      _isCheckingProfileId = false;
    });
  }

  Future<void> _syncPushToken() async {
    if (_isSyncingPushToken) {
      return;
    }
    _isSyncingPushToken = true;
    try {
      await _pushRegistrationService.registerCurrentDeviceToken();
    } catch (_) {
      // Do not disrupt the dashboard if push registration fails.
    } finally {
      _isSyncingPushToken = false;
    }
  }

  void _scheduleUnreadSync() {
    if (_isCheckingUnreadSync || _isLoadingNotifications) {
      return;
    }
    final now = DateTime.now();
    if (_lastUnreadSyncAt != null &&
        now.difference(_lastUnreadSyncAt!) < const Duration(seconds: 20)) {
      return;
    }

    _isCheckingUnreadSync = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _refreshUnreadNotifications().whenComplete(() {
        _lastUnreadSyncAt = DateTime.now();
        _isCheckingUnreadSync = false;
      });
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

  Future<void> _refreshUnreadNotifications() async {
    if (_isLoadingNotifications) {
      return;
    }

    setState(() {
      _isLoadingNotifications = true;
    });

    try {
      final unread = await _notificationService.fetchAll(status: 'unread');
      if (!mounted) {
        return;
      }
      setState(() {
        _unreadNotificationCount = unread.length;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _unreadNotificationCount = 0;
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoadingNotifications = false;
        });
      }
    }
  }

  Future<void> _openNotificationsCenter() async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => NotificationsCenterScreen(
          service: _notificationService,
        ),
      ),
    );
    await _refreshUnreadNotifications();
  }

  @override
  Widget build(BuildContext context) {
    _scheduleProfileIdSync();
    _scheduleUnreadSync();
    final secondaryColor = Theme.of(context).colorScheme.secondary;

    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(10),
              child: Image.asset(
                'assets/AnakUnggul-logo.png',
                width: 34,
                height: 34,
                fit: BoxFit.contain,
              ),
            ),
            const SizedBox(width: NeuroColors.spacingSm),
            const Text('AnakUnggul'),
          ],
        ),
        actions: [
          IconButton(
            onPressed: _openNotificationsCenter,
            tooltip: 'Notifications',
            icon: Stack(
              clipBehavior: Clip.none,
              children: [
                const Icon(Icons.notifications_none),
                if (_unreadNotificationCount > 0)
                  Positioned(
                    right: -6,
                    top: -4,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 5, vertical: 1),
                      decoration: BoxDecoration(
                        color: Colors.red.shade500,
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: Text(
                        _unreadNotificationCount > 99
                            ? '99+'
                            : '$_unreadNotificationCount',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(NeuroColors.spacingLg),
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  const _ConnectionDot(),
                  const SizedBox(width: NeuroColors.spacingSm),
                  Text(
                    'Online',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: secondaryColor,
                          fontWeight: FontWeight.w600,
                        ),
                  ),
                ],
              ),
              const SizedBox(height: NeuroColors.spacingMd),
              const _BrandHeaderCard(),
              const SizedBox(height: NeuroColors.spacingMd),
              const _MascotCarousel(),
              const SizedBox(height: NeuroColors.spacingLg),
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
              const SizedBox(height: NeuroColors.spacingMd),
              _LatestSessionCard(
                summary: _latestSummary,
                isLoading: _isLoadingSummary,
                onRefresh: _refreshLatestSummary,
                onViewHistory: () async {
                  await Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) =>
                          HistoryInsightsScreen(service: _summaryService),
                    ),
                  );
                  await _refreshLatestSummary();
                },
              ),
              const SizedBox(height: NeuroColors.spacingLg),
              ElevatedButton.icon(
                onPressed: widget.onGoSupport,
                icon: const Icon(Icons.support_agent),
                label: const Text('GO TO LIVE SUPPORT'),
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
    required this.onViewHistory,
  });

  final SessionSummary? summary;
  final bool isLoading;
  final Future<void> Function() onRefresh;
  final VoidCallback onViewHistory;

  @override
  Widget build(BuildContext context) {
    final surfaceColor = Theme.of(context).colorScheme.surface;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(NeuroColors.spacingMd),
      decoration: BoxDecoration(
        color: surfaceColor,
        borderRadius: BorderRadius.circular(NeuroColors.radiusMd),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.history_edu, color: NeuroColors.primary),
              const SizedBox(width: NeuroColors.spacingSm),
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
          const SizedBox(height: NeuroColors.spacingSm),
          if (summary == null) ...[
            Text(
              'No completed session yet. Run live support and return to dashboard.',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ] else ...[
            Text(
              summary!.title,
              style: Theme.of(context).textTheme.titleSmall,
            ),
            const SizedBox(height: 4),
            Text(
              'Duration ${summary!.durationMinutes} min • ${_formatUtc(summary!.timestampUtc)}',
              style: Theme.of(context).textTheme.bodyMedium,
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
          const SizedBox(height: NeuroColors.spacingMd),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: onViewHistory,
              icon: const Icon(Icons.history),
              label: const Text('VIEW HISTORY / INSIGHTS'),
            ),
          ),
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

class _BrandHeaderCard extends StatelessWidget {
  const _BrandHeaderCard();

  @override
  Widget build(BuildContext context) {
    final surfaceColor = Theme.of(context).colorScheme.surface;
    final bodyStyle = Theme.of(context).textTheme.bodyMedium?.copyWith(
          color: NeuroColors.textSecondary,
        );

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(
        horizontal: NeuroColors.spacingMd,
        vertical: NeuroColors.spacingLg,
      ),
      decoration: BoxDecoration(
        color: surfaceColor,
        borderRadius: BorderRadius.circular(NeuroColors.radiusMd),
      ),
      child: Column(
        children: [
          Image.asset(
            'assets/AnakUnggul-logo.png',
            width: 80,
            height: 80,
            fit: BoxFit.contain,
          ),
          const SizedBox(height: NeuroColors.spacingSm),
          Text(
            'Real-time caregiver support for calm,\nguided responses during difficult sensory moments.',
            textAlign: TextAlign.center,
            style: bodyStyle,
          ),
        ],
      ),
    );
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
    final surfaceColor = Theme.of(context).colorScheme.surface;
    final title = profile?.name.isNotEmpty == true
        ? profile!.name
        : hasProfile
            ? profileId!
            : 'No support profile selected';

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(NeuroColors.spacingMd),
      decoration: BoxDecoration(
        color: surfaceColor,
        borderRadius: BorderRadius.circular(NeuroColors.radiusMd),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.badge_outlined, color: NeuroColors.primary),
              const SizedBox(width: NeuroColors.spacingSm),
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
          const SizedBox(height: NeuroColors.spacingSm),
          Text(title, style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: NeuroColors.spacingSm),
          if (!hasProfile)
            Text(
              'Set a profile in Support to help Buddy remember who is being supported and what usually helps.',
              style: Theme.of(context).textTheme.bodyMedium,
            )
          else ...[
            Text(
              profile?.notes.isNotEmpty == true
                  ? profile!.notes
                  : 'Profile is active. Add a short support summary and a few memory notes to make later sessions more personalized.',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: NeuroColors.spacingMd),
            Wrap(
              spacing: NeuroColors.spacingSm,
              runSpacing: NeuroColors.spacingSm,
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
          const SizedBox(height: NeuroColors.spacingMd),
          SizedBox(
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
    final chipColor =
        Theme.of(context).colorScheme.primary.withValues(alpha: 0.10);
    final chipTextColor = Theme.of(context).textTheme.titleSmall?.color ??
        Theme.of(context).colorScheme.onSurface;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: chipColor,
        borderRadius: BorderRadius.circular(NeuroColors.radiusSm),
      ),
      child: Text(
        '$label: $value',
        style: TextStyle(
          color: chipTextColor,
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
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: Theme.of(context).colorScheme.secondary,
        ),
      ),
    );
  }
}

// ── Mascot Carousel ──

class _MascotCarousel extends StatefulWidget {
  const _MascotCarousel();

  @override
  State<_MascotCarousel> createState() => _MascotCarouselState();
}

class _MascotCarouselState extends State<_MascotCarousel> {
  final PageController _pageController = PageController();
  Timer? _autoSlideTimer;
  int _currentPage = 0;

  static const List<_CarouselSlide> _slides = [
    _CarouselSlide(
      asset: 'assets/mascot01.png',
      title: 'Hello. Wishing you a calm day.',
      subtitle:
          'Review the latest session, check insights, and open Live Support when you need real-time guidance.',
    ),
    _CarouselSlide(
      asset: 'assets/mascot02.png',
      title: 'Buddy is here for you.',
      subtitle:
          'Your AI companion observes, listens, and offers calm guidance during moments that matter most.',
    ),
  ];

  @override
  void initState() {
    super.initState();
    _autoSlideTimer = Timer.periodic(const Duration(seconds: 5), (_) {
      if (!mounted || !_pageController.hasClients || _slides.length < 2) {
        return;
      }
      final nextPage = (_currentPage + 1) % _slides.length;
      _pageController.animateToPage(
        nextPage,
        duration: const Duration(milliseconds: 850),
        curve: Curves.easeInOutCubic,
      );
    });
  }

  @override
  void dispose() {
    _autoSlideTimer?.cancel();
    _pageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final surfaceColor = Theme.of(context).colorScheme.surface;
    final inactiveDotColor =
        Theme.of(context).colorScheme.primary.withValues(alpha: 0.18);

    return Column(
      children: [
        Container(
          decoration: BoxDecoration(
            color: surfaceColor,
            borderRadius: BorderRadius.circular(NeuroColors.radiusMd),
          ),
          child: Column(
            children: [
              SizedBox(
                height: 324,
                child: PageView.builder(
                  controller: _pageController,
                  itemCount: _slides.length,
                  onPageChanged: (index) {
                    setState(() => _currentPage = index);
                  },
                  itemBuilder: (context, index) {
                    final slide = _slides[index];
                    return Padding(
                      padding: const EdgeInsets.all(NeuroColors.spacingMd),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Center(
                            child: AnimatedSwitcher(
                              duration: const Duration(milliseconds: 400),
                              child: ClipRRect(
                                key: ValueKey(slide.asset),
                                borderRadius:
                                    BorderRadius.circular(NeuroColors.radiusMd),
                                child: Image.asset(
                                  slide.asset,
                                  width: 110,
                                  height: 110,
                                  fit: BoxFit.cover,
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(height: NeuroColors.spacingSm),
                          Text(
                            slide.title,
                            style: Theme.of(context).textTheme.headlineSmall,
                          ),
                          const SizedBox(height: NeuroColors.spacingSm),
                          Text(
                            slide.subtitle,
                            style: const TextStyle(
                                color: NeuroColors.textSecondary),
                          ),
                        ],
                      ),
                    );
                  },
                ),
              ),
              Padding(
                padding: const EdgeInsets.only(bottom: NeuroColors.spacingMd),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: List.generate(
                    _slides.length,
                    (index) => AnimatedContainer(
                      duration: const Duration(milliseconds: 300),
                      margin: const EdgeInsets.symmetric(horizontal: 4),
                      width: _currentPage == index ? 24 : 8,
                      height: 8,
                      decoration: BoxDecoration(
                        color: _currentPage == index
                            ? Theme.of(context).colorScheme.primary
                            : inactiveDotColor,
                        borderRadius:
                            BorderRadius.circular(NeuroColors.radiusPill),
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _CarouselSlide {
  const _CarouselSlide({
    required this.asset,
    required this.title,
    required this.subtitle,
  });

  final String asset;
  final String title;
  final String subtitle;
}
