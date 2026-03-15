import 'package:camera/camera.dart';
import 'package:flutter/material.dart';

import '../../theme/app_theme.dart';

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

  String _selectedGuide = 'overview';
  int _phraseIndex = 0;
  bool _isChangingTheme = false;

  static const List<String> _phrases = [
    'Hi! I am Neuro Buddy. Let us keep this moment calm and safe.',
    'Great job. You did your best today, and that matters.',
    'Try this breathing rhythm: inhale for 4, hold for 7, exhale for 8.',
    'You are not alone. I am right here with you.',
  ];

  @override
  void initState() {
    super.initState();
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
  }

  @override
  void dispose() {
    _floatController.dispose();
    _pulseController.dispose();
    super.dispose();
  }

  void _onTapMascot() {
    setState(() {
      _phraseIndex = (_phraseIndex + 1) % _phrases.length;
    });
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

  String get _themeLabel {
    switch (widget.themeSelection) {
      case AppVisualTheme.dark:
        return 'Dark';
      case AppVisualTheme.pink:
        return 'Soft Pink';
      case AppVisualTheme.light:
        return 'Light';
    }
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

  String get _guideTitle {
    switch (_selectedGuide) {
      case 'breathe':
        return 'Breathe with Buddy';
      case 'privacy':
        return 'Privacy & Safety';
      case 'overview':
      default:
        return 'What is NeuroDecode?';
    }
  }

  String get _guideBody {
    switch (_selectedGuide) {
      case 'breathe':
        return 'Try this together: inhale for 4, hold for 4, exhale slowly for 6. Repeat three times. Keep your voice soft and your steps simple.';
      case 'privacy':
        return 'Camera and microphone are used only during Live Support to help generate calm, real-time guidance. NeuroDecode is a support tool, not a medical diagnosis tool.';
      case 'overview':
      default:
        return 'I am your real-time support companion. When a sensory overload or crisis begins, open the Support tab, turn on camera and microphone, and place the phone nearby. I will listen, observe, and offer short calming guidance to help you and your child through the moment.';
    }
  }

  @override
  Widget build(BuildContext context) {
    final surfaceColor = Theme.of(context).colorScheme.surface;
    final backgroundColor = Theme.of(context).scaffoldBackgroundColor;
    final primaryColor = Theme.of(context).colorScheme.primary;

    return Scaffold(
      backgroundColor: backgroundColor,
      appBar: AppBar(
        title: const Text('Meet Buddy!'),
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
            child: AnimatedBuilder(
              animation: _floatAnimation,
              builder: (context, child) {
                return Transform.translate(
                  offset: Offset(0, _floatAnimation.value),
                  child: ScaleTransition(
                    scale: _pulseAnimation,
                    child: child,
                  ),
                );
              },
              child: Container(
                padding: const EdgeInsets.all(NeuroColors.spacingMd),
                decoration: BoxDecoration(
                  color: surfaceColor,
                  borderRadius: BorderRadius.circular(NeuroColors.radiusMd),
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(14),
                  child: Image.asset(
                    'assets/mascot02.png',
                    height: 260,
                    fit: BoxFit.contain,
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: 16),
          Text(
            'Tap Buddy to wave hello',
            textAlign: TextAlign.center,
            style: TextStyle(color: primaryColor, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: NeuroColors.spacingMd - 2),
          Container(
            padding: const EdgeInsets.all(NeuroColors.spacingMd),
            decoration: BoxDecoration(
              color: surfaceColor,
              borderRadius: BorderRadius.circular(NeuroColors.radiusMd),
            ),
            child: Column(
              children: [
                Text(
                  'Hi! I am Buddy',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 32,
                    fontWeight: FontWeight.w700,
                    color: primaryColor,
                  ),
                ),
                const SizedBox(height: NeuroColors.spacingSm),
                Text(
                  _phrases[_phraseIndex],
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    height: 1.5,
                    fontSize: 16,
                  ),
                ),
                const SizedBox(height: NeuroColors.spacingMd - 2),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  alignment: WrapAlignment.center,
                  children: [
                    _BuddyActionChip(
                      label: 'How it works',
                      selected: _selectedGuide == 'overview',
                      onPressed: () =>
                          setState(() => _selectedGuide = 'overview'),
                    ),
                    _BuddyActionChip(
                      label: 'Breathe',
                      selected: _selectedGuide == 'breathe',
                      onPressed: () =>
                          setState(() => _selectedGuide = 'breathe'),
                    ),
                    _BuddyActionChip(
                      label: 'Privacy',
                      selected: _selectedGuide == 'privacy',
                      onPressed: () =>
                          setState(() => _selectedGuide = 'privacy'),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: NeuroColors.spacingMd - 2),
          Container(
            padding: const EdgeInsets.all(NeuroColors.spacingMd + 2),
            decoration: BoxDecoration(
              color: surfaceColor,
              borderRadius: BorderRadius.circular(NeuroColors.radiusMd),
            ),
            child: ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Icon(
                Icons.palette_outlined,
                color: Theme.of(context).colorScheme.primary,
              ),
              title: Text(
                'Theme Mood',
                style: Theme.of(context).textTheme.titleSmall,
              ),
              subtitle: Text(
                _themeLabel,
                style: Theme.of(context).textTheme.bodySmall,
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: _isChangingTheme ? null : _openThemeMenu,
            ),
          ),
          if (_isChangingTheme) ...[
            const SizedBox(height: NeuroColors.spacingSm),
            const LinearProgressIndicator(minHeight: 3),
          ],
          const SizedBox(height: NeuroColors.spacingMd - 2),
          Container(
            padding: const EdgeInsets.all(NeuroColors.spacingMd + 2),
            decoration: BoxDecoration(
              color: surfaceColor,
              borderRadius: BorderRadius.circular(NeuroColors.radiusMd),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _guideTitle,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(fontSize: 22),
                ),
                const SizedBox(height: NeuroColors.spacingSm + 2),
                Text(
                  _guideBody,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    height: 1.55,
                  ),
                ),
                const SizedBox(height: NeuroColors.spacingMd - 2),
                // Text(
                //   'Use the Support tab below whenever you need live help.',
                //   style: TextStyle(
                //     color: const Color(0xFF6EA1D5).withValues(alpha: 0.95),
                //     fontWeight: FontWeight.w600,
                //   ),
                // ),
              ],
            ),
          ),
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
