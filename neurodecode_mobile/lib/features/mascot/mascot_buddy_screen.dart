import 'dart:ui';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../config/app_identity_store.dart';
import '../../theme/app_theme.dart';
import '../profile/profile_memory_service.dart';
import 'daily_checkin_service.dart';

class MascotBuddyScreen extends StatefulWidget {
  const MascotBuddyScreen({
    super.key,
    required this.cameras,
    required this.themeSelection,
    required this.onThemeChanged,
    required this.onGoHome,
    required this.onGoSupport,
  });

  final List<CameraDescription> cameras;
  final AppVisualTheme themeSelection;
  final Future<void> Function(AppVisualTheme theme) onThemeChanged;
  final VoidCallback onGoHome;
  final VoidCallback onGoSupport;

  @override
  State<MascotBuddyScreen> createState() => _MascotBuddyScreenState();
}

class _MascotBuddyScreenState extends State<MascotBuddyScreen>
    with TickerProviderStateMixin {
  late final AnimationController _pulseController;
  late final Animation<double> _pulseAnimation;
  late final AnimationController _floatController;
  late final Animation<double> _floatAnimation;
  late final AnimationController _entranceController;

  Offset _tiltOffset = Offset.zero;

  bool _isChangingTheme = false;
  String? _activeProfileId;
  String? _activeProfileName;
  final ProfileMemoryService _profileMemoryService = ProfileMemoryService();
  final DailyCheckinService _checkinService = DailyCheckinService();

  // Selected quick chips
  final Set<String> _selectedChips = {};
  final TextEditingController _notesController = TextEditingController();
  bool _isSaving = false;

  final List<String> _checkInChips = [
    'Everything calm',
    'Sensory overload',
    'Mild meltdown',
    'Hard to sleep',
    'Big transition difficulty',
    'New trigger noticed',
  ];

  late List<String> _phrases = [
    'Hi! I am Neuro Buddy. How was today?',
    'Take a deep breath. I am listening.',
    'You are doing great.',
  ];

  @override
  void initState() {
    super.initState();
    _loadContext();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 700),
    );
    _pulseAnimation = Tween<double>(begin: 1.0, end: 1.06).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
    _floatController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2400),
    )..repeat(reverse: true);
    _floatAnimation = Tween<double>(begin: -8, end: 8).animate(
      CurvedAnimation(parent: _floatController, curve: Curves.easeInOut),
    );
    _entranceController = AnimationController(
        vsync: this,
        duration: const Duration(milliseconds: 1400),
    )..forward();
  }

  Future<void> _loadContext() async {
    final store = AppIdentityStore();
    final profileId = await store.getActiveProfileId();
    if (!mounted || profileId == null || profileId.isEmpty) {
      return;
    }

    var profileLabel = profileId;
    try {
      final profile = await _profileMemoryService.fetchProfile(profileId);
      final preferredName = profile?.childName.trim();
      final fallbackName = profile?.name.trim();
      if (preferredName != null && preferredName.isNotEmpty) {
        profileLabel = preferredName;
      } else if (fallbackName != null && fallbackName.isNotEmpty) {
        profileLabel = fallbackName;
      }
    } catch (_) {
      // Keep the profile id fallback if profile details are unavailable.
    }

    if (mounted) {
      setState(() {
        _activeProfileId = profileId;
        _activeProfileName = profileLabel;
        _phrases = [
          'Hi, how was $_activeProfileName\'s day today?',
          'Take a deep breath. How is $_activeProfileName feeling?',
          'I am here to help you reflect on $_activeProfileName\'s day.',
        ];
      });
    }
  }

  @override
  void dispose() {
    _notesController.removeListener(_handleNotesChanged);
    _notesController.dispose();
    _entranceController.dispose();
    _floatController.dispose();
    _pulseController.dispose();
    super.dispose();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _notesController.removeListener(_handleNotesChanged);
    _notesController.addListener(_handleNotesChanged);
  }

  void _handleNotesChanged() {
    if (mounted) {
      setState(() {});
    }
  }

  void _onTapMascot() {
    HapticFeedback.selectionClick();
    _phrases.shuffle();
    setState(() {}); 
    _pulseController
      ..stop()
      ..forward(from: 0.0)
      ..reverse();
  }

  Future<void> _handleThemeChange(AppVisualTheme nextTheme) async {
    if (_isChangingTheme || widget.themeSelection == nextTheme) {
      return;
    }
    setState(() {
      _isChangingTheme = true;
    });
    try {
      await widget.onThemeChanged(nextTheme);
    } finally {
      if (mounted) {
        setState(() {
          _isChangingTheme = false;
        });
      }
    }
  }

  Future<void> _saveCheckIn() async {
    if (_selectedChips.isEmpty && _notesController.text.trim().isEmpty) return;

    setState(() {
      _isSaving = true;
    });

    final profileId = _activeProfileId;
    final shouldSuggestMemory = _selectedChips.any(chipSuggestsMemory);

    try {
      if (profileId != null) {
        await _checkinService.saveCheckin(
          profileId: profileId,
          chips: _selectedChips.toList(),
          notes: _notesController.text.trim(),
        );
      }
    } catch (_) {
      // Local save failure should not block the UX.
    }

    if (mounted) {
      setState(() {
        _isSaving = false;
      });

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Daily check-in saved.')),
      );

      if (shouldSuggestMemory && profileId != null) {
        _showMemorySuggestionDialog();
      } else {
        _clearForm();
      }
    }
  }

  void _clearForm() {
    setState(() {
      _selectedChips.clear();
      _notesController.clear();
    });
  }

  Future<void> _showMemorySuggestionDialog() async {
    // Build the most specific category from the first flagged chip.
    final flaggedChip = _selectedChips.firstWhere(
      chipSuggestsMemory,
      orElse: () => _selectedChips.first,
    );
    final suggestedCategory = chipToMemoryCategory(flaggedChip);

    // Pre-fill the note with only the flagged chips, not unrelated ones.
    final flaggedChips = _selectedChips.where(chipSuggestsMemory).toList();
    final preFilledNote = flaggedChips.isNotEmpty
        ? flaggedChips.join(', ')
        : _selectedChips.join(', ');
    final noteController = TextEditingController(text: preFilledNote);

    await showDialog<void>(
      context: context,
      builder: (ctx) {
        return AlertDialog(
          title: const Text('Add to Profile Memory?'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                  'You noted some challenges today. Saving this to memory helps Neu Buddy adapt in the future.'),
              const SizedBox(height: 12),
              TextField(
                controller: noteController,
                decoration: const InputDecoration(labelText: 'Observation notes'),
                maxLines: 2,
              ),
              const SizedBox(height: 8),
              Text(
                'Category: $suggestedCategory',
                style: TextStyle(
                  fontSize: 12,
                  color: Theme.of(ctx).colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.of(ctx).pop();
                _clearForm();
              },
              child: const Text('Skip'),
            ),
            FilledButton(
              onPressed: () async {
                Navigator.of(ctx).pop();
                setState(() => _isSaving = true);
                try {
                  await _profileMemoryService.addMemory(
                    profileId: _activeProfileId!,
                    category: suggestedCategory,
                    note: noteController.text,
                    confidence: 'medium',
                  );
                  if (mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Profile Memory updated.')),
                    );
                  }
                } catch (e) {
                  if (mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text('Failed to save memory: $e')),
                    );
                  }
                } finally {
                  if (mounted) setState(() => _isSaving = false);
                  _clearForm();
                }
              },
              child: const Text('Save to Memory'),
            ),
          ],
        );
      },
    );
  }

  Future<void> _openThemeMenu() async {
    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      backgroundColor: Theme.of(context).colorScheme.surface,
      builder: (sheetContext) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Theme Mood',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: NeuroColors.spacingSm),
                Text(
                  'Choose the look that feels the calmest for you.',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
                const SizedBox(height: NeuroColors.spacingMd),
                _ThemeMenuTile(
                  title: 'Light',
                  subtitle: 'Clean and airy',
                  colors: const [
                    NeuroColors.background,
                    NeuroColors.primary,
                    NeuroColors.secondary,
                  ],
                  selected: widget.themeSelection == AppVisualTheme.light,
                  onTap: () async {
                    Navigator.pop(sheetContext);
                    await _handleThemeChange(AppVisualTheme.light);
                  },
                ),
                _ThemeMenuTile(
                  title: 'Dark',
                  subtitle: 'Balanced and focused',
                  colors: const [
                    NeuroColors.darkBackground,
                    NeuroColors.darkPrimary,
                    NeuroColors.darkSecondary,
                  ],
                  selected: widget.themeSelection == AppVisualTheme.dark,
                  onTap: () async {
                    Navigator.pop(sheetContext);
                    await _handleThemeChange(AppVisualTheme.dark);
                  },
                ),
                _ThemeMenuTile(
                  title: 'Soft Pink',
                  subtitle: 'Warm and gentle',
                  colors: const [
                    NeuroColors.pinkBackground,
                    NeuroColors.pinkPrimary,
                    NeuroColors.pinkSecondary,
                  ],
                  selected: widget.themeSelection == AppVisualTheme.pink,
                  onTap: () async {
                    Navigator.pop(sheetContext);
                    await _handleThemeChange(AppVisualTheme.pink);
                  },
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final surfaceColor = Theme.of(context).colorScheme.surface;
    final backgroundColor = Theme.of(context).scaffoldBackgroundColor;
    final primaryColor = Theme.of(context).colorScheme.primary;

    return Scaffold(
      backgroundColor: backgroundColor,
      appBar: AppBar(
        title: const Text('Daily Check-in'),
        backgroundColor: backgroundColor,
        actions: [
          IconButton(
            onPressed: _isChangingTheme ? null : _openThemeMenu,
            tooltip: 'Theme mood',
            icon: const Icon(Icons.tune),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 20),
        children: [
          GestureDetector(
            onTap: _onTapMascot,
            onPanUpdate: (details) {
              setState(() {
                _tiltOffset += details.delta * 0.05;
                _tiltOffset = Offset(
                  _tiltOffset.dx.clamp(-15.0, 15.0),
                  _tiltOffset.dy.clamp(-15.0, 15.0),
                );
              });
            },
            onPanEnd: (_) {
              setState(() {
                _tiltOffset = Offset.zero;
              });
            },
            child: AnimatedBuilder(
              animation: _floatAnimation,
              builder: (context, _) {
                return Transform.translate(
                  offset: Offset(_tiltOffset.dx, _floatAnimation.value + _tiltOffset.dy),
                  child: ScaleTransition(
                    scale: _pulseAnimation,
                    child: Stack(
                      alignment: Alignment.center,
                      children: [
                        // Soft glow background
                        Container(
                          width: 200,
                          height: 200,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            boxShadow: [
                              BoxShadow(
                                color: primaryColor.withValues(alpha: 0.15),
                                blurRadius: 40,
                                spreadRadius: 20,
                              ),
                            ],
                          ),
                        ),
                        // Glass card container
                        Container(
                          padding: const EdgeInsets.all(NeuroColors.spacingMd),
                          decoration: BoxDecoration(
                            color: surfaceColor.withValues(alpha: 0.8),
                            borderRadius: BorderRadius.circular(NeuroColors.radiusMd),
                            border: Border.all(
                              color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.1),
                              width: 1,
                            ),
                          ),
                          child: ClipRRect(
                            borderRadius: BorderRadius.circular(14),
                            child: BackdropFilter(
                              filter: ImageFilter.blur(sigmaX: 8, sigmaY: 8),
                              child: Image.asset(
                                'assets/mascot02.png',
                                height: 260,
                                fit: BoxFit.contain,
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 16),
          AnimatedGlassCard(
            animation: _entranceController,
            delay: 0.0,
            child: Text(
              'Tap Buddy to interact',
              textAlign: TextAlign.center,
              style: TextStyle(color: primaryColor, fontWeight: FontWeight.w600),
            ),
          ),
          AnimatedGlassCard(
            animation: _entranceController,
            delay: 0.1,
            child: Column(
              children: [
                Text(
                  'Daily Journal',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 28,
                    fontWeight: FontWeight.w700,
                    color: primaryColor,
                  ),
                ),
                const SizedBox(height: NeuroColors.spacingSm),
                AnimatedSwitcher(
                  duration: const Duration(milliseconds: 400),
                  transitionBuilder: (child, animation) {
                    return FadeTransition(opacity: animation, child: child);
                  },
                  child: Text(
                    key: ValueKey<String>(_phrases.first),
                    _phrases.first,
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      height: 1.5,
                      fontSize: 16,
                    ),
                  ),
                ),
                const SizedBox(height: NeuroColors.spacingLg),
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  alignment: WrapAlignment.center,
                  children: _checkInChips.map((chipLabel) {
                    final isSelected = _selectedChips.contains(chipLabel);
                    return _BuddyActionChip(
                      label: chipLabel,
                      selected: isSelected,
                      onPressed: () {
                        HapticFeedback.lightImpact();
                        setState(() {
                          if (isSelected) {
                            _selectedChips.remove(chipLabel);
                          } else {
                            _selectedChips.add(chipLabel);
                          }
                        });
                      },
                    );
                  }).toList(),
                ),
                const SizedBox(height: NeuroColors.spacingLg),
                // Optional Note Field
                TextField(
                  controller: _notesController,
                  maxLines: 3,
                  decoration: InputDecoration(
                    hintText: 'Any extra notes about today?',
                    filled: true,
                    fillColor: surfaceColor,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(NeuroColors.radiusMd),
                      borderSide: BorderSide.none,
                    ),
                  ),
                ),
                const SizedBox(height: NeuroColors.spacingLg),
                SizedBox(
                  width: double.infinity,
                  height: 52,
                  child: FilledButton.icon(
                    onPressed: _isSaving 
                      ? null 
                      : (_selectedChips.isNotEmpty || _notesController.text.trim().isNotEmpty ? _saveCheckIn : null),
                    icon: _isSaving 
                      ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                      : const Icon(Icons.check),
                    label: Text(_isSaving ? 'Saving...' : 'Save Check-in'),
                    style: FilledButton.styleFrom(
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(NeuroColors.radiusLg),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
          if (_isChangingTheme) ...[
            const SizedBox(height: NeuroColors.spacingSm),
            const LinearProgressIndicator(minHeight: 3),
          ],
        ],
      ),
    );
  }
}

class _BuddyActionChip extends StatelessWidget {
  const _BuddyActionChip({
    required this.label,
    required this.selected,
    required this.onPressed,
  });

  final String label;
  final bool selected;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final selectedColor = Theme.of(context).colorScheme.primary;
    final unselectedColor = Theme.of(context).colorScheme.primary.withValues(alpha: 0.10);

    return ActionChip(
      onPressed: onPressed,
      backgroundColor:
          selected ? selectedColor : unselectedColor,
      side: BorderSide.none,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
      label: Text(
        label,
        style: TextStyle(
          color: selected ? Colors.white : selectedColor,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

class _ThemeMenuTile extends StatelessWidget {
  const _ThemeMenuTile({
    required this.title,
    required this.subtitle,
    required this.colors,
    required this.selected,
    required this.onTap,
  });

  final String title;
  final String subtitle;
  final List<Color> colors;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(NeuroColors.radiusMd),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 220),
        margin: const EdgeInsets.only(bottom: NeuroColors.spacingSm),
        padding: const EdgeInsets.all(NeuroColors.spacingSm + 4),
        decoration: BoxDecoration(
          color: selected
              ? Theme.of(context).colorScheme.primary.withValues(alpha: 0.08)
              : Theme.of(context).colorScheme.surface,
          borderRadius: BorderRadius.circular(NeuroColors.radiusMd),
          border: Border.all(
            color: selected
                ? Theme.of(context).colorScheme.primary
                : Theme.of(context).colorScheme.outline.withValues(alpha: 0.18),
            width: selected ? 1.8 : 1,
          ),
        ),
        child: Row(
          children: [
            Row(
              children: colors
                  .map(
                    (color) => Container(
                      width: 16,
                      height: 16,
                      margin: const EdgeInsets.only(right: 4),
                      decoration: BoxDecoration(
                        color: color,
                        shape: BoxShape.circle,
                        border: Border.all(color: Colors.white, width: 1),
                      ),
                    ),
                  )
                  .toList(growable: false),
            ),
            const SizedBox(width: NeuroColors.spacingMd),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                  const SizedBox(height: NeuroColors.spacingXs),
                  Text(
                    subtitle,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
            if (selected)
              Icon(
                Icons.check_circle,
                size: 20,
                color: Theme.of(context).colorScheme.primary,
              )
            else
              Icon(
                Icons.radio_button_unchecked,
                size: 20,
                color: Theme.of(context)
                    .colorScheme
                    .outline
                    .withValues(alpha: 0.45),
              ),
          ],
        ),
      ),
    );
  }
}

class AnimatedGlassCard extends StatelessWidget {
  const AnimatedGlassCard({
    super.key,
    required this.child,
    required this.animation,
    this.delay = 0.0,
  });

  final Widget child;
  final Animation<double> animation;
  final double delay;

  @override
  Widget build(BuildContext context) {
    final start = delay;
    final end = (delay + 0.4).clamp(0.0, 1.0);
    
    return FadeTransition(
      opacity: CurvedAnimation(
        parent: animation,
        curve: Interval(start, end, curve: Curves.easeOut),
      ),
      child: SlideTransition(
        position: Tween<Offset>(begin: const Offset(0, 0.05), end: Offset.zero).animate(
          CurvedAnimation(
            parent: animation,
            curve: Interval(start, end, curve: Curves.easeOutCubic),
          ),
        ),
        child: Container(
          margin: const EdgeInsets.only(bottom: NeuroColors.spacingMd - 2),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(NeuroColors.radiusMd),
            boxShadow: [
              BoxShadow(
                color: Theme.of(context).shadowColor.withValues(alpha: 0.05),
                blurRadius: 20,
                offset: const Offset(0, 10),
              )
            ],
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(NeuroColors.radiusMd),
            child: BackdropFilter(
              filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
              child: Container(
                padding: const EdgeInsets.all(NeuroColors.spacingMd + 2),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.surface.withValues(alpha: 0.65),
                  borderRadius: BorderRadius.circular(NeuroColors.radiusMd),
                  border: Border.all(
                    color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.15),
                    width: 1,
                  ),
                ),
                child: child,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
