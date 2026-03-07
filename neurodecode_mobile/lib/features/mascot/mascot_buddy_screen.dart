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

  int _phraseIndex = 0;
  static const List<String> _phrases = [
    'Hi! I am Neuro Buddy! You can call me Neu.. Let us keep this moment calm and safe.',
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
      CurvedAnimation(
        parent: _pulseController,
        curve: Curves.easeInOut,
      ),
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
            style: TextStyle(color: Color(0xFF7BA6D4), fontWeight: FontWeight.w600),
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
                const SizedBox(height: 12),
                const Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  alignment: WrapAlignment.center,
                  children: [
                    _BuddyTag(label: 'Friendly'),
                    _BuddyTag(label: 'Caring'),
                    _BuddyTag(label: 'Fun'),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          SizedBox(
            height: 56,
            child: ElevatedButton.icon(
              onPressed: widget.onGoHome,
              icon: const Icon(Icons.home),
              label: const Text('Back to Home'),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF75A9DE),
                foregroundColor: Colors.white,
              ),
            ),
          ),
          const SizedBox(height: 10),
          SizedBox(
            height: 50,
            child: OutlinedButton.icon(
              onPressed: widget.onGoSupport,
              icon: const Icon(Icons.support_agent),
              label: const Text('Start Live Support'),
            ),
          ),
        ],
      ),
    );
  }
}

class _BuddyTag extends StatelessWidget {
  const _BuddyTag({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: const Color(0xFFE9F0FB),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: const TextStyle(
          color: Color(0xFF75A9DE),
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
