import 'package:camera/camera.dart';
import 'package:flutter/material.dart';

class MascotBuddyScreen extends StatefulWidget {
  const MascotBuddyScreen({
    super.key,
    required this.cameras,
    required this.onGoHome,
    required this.onGoSupport,
  });

  final List<CameraDescription> cameras;
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
    return Scaffold(
      backgroundColor: const Color(0xFFF7F2EA),
      appBar: AppBar(
        title: const Text('Meet Buddy!'),
        backgroundColor: const Color(0xFFF7F2EA),
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
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(18),
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
          const Text(
            'Tap Buddy to wave hello',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Color(0xFF7BA6D4),
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 14),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(18),
            ),
            child: Column(
              children: [
                const Text(
                  'Hi! I am Buddy! 👋',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 34,
                    fontWeight: FontWeight.w700,
                    color: Color(0xFF75A9DE),
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  _phrases[_phraseIndex],
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: Color(0xFF607585),
                    height: 1.5,
                    fontSize: 16,
                  ),
                ),
                const SizedBox(height: 14),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  alignment: WrapAlignment.center,
                  children: [
                    _BuddyActionChip(
                      label: 'How it works',
                      selected: _selectedGuide == 'overview',
                      onPressed: () => setState(() => _selectedGuide = 'overview'),
                    ),
                    _BuddyActionChip(
                      label: 'Breathe',
                      selected: _selectedGuide == 'breathe',
                      onPressed: () => setState(() => _selectedGuide = 'breathe'),
                    ),
                    _BuddyActionChip(
                      label: 'Privacy',
                      selected: _selectedGuide == 'privacy',
                      onPressed: () => setState(() => _selectedGuide = 'privacy'),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(18),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _guideTitle,
                  style: const TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w700,
                    color: Color(0xFF2F4761),
                  ),
                ),
                const SizedBox(height: 10),
                Text(
                  _guideBody,
                  style: const TextStyle(
                    color: Color(0xFF607585),
                    height: 1.55,
                    fontSize: 15,
                  ),
                ),
                const SizedBox(height: 14),
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
    return ActionChip(
      onPressed: onPressed,
      backgroundColor:
          selected ? const Color(0xFF75A9DE) : const Color(0xFFE9F0FB),
      side: BorderSide.none,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
      label: Text(
        label,
        style: TextStyle(
          color: selected ? Colors.white : const Color(0xFF75A9DE),
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
