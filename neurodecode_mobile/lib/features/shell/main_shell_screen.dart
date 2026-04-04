import 'package:camera/camera.dart';
import 'package:flutter/material.dart';

import '../clinical/find_help_screen.dart';
import '../home/home_dashboard_screen.dart';
import '../mascot/mascot_buddy_screen.dart';
import '../support/support_hub_screen.dart';
import '../../theme/app_theme.dart';

class MainShellScreen extends StatefulWidget {
  const MainShellScreen({
    super.key,
    required this.cameras,
    required this.themeSelection,
    required this.onThemeChanged,
  });

  final List<CameraDescription> cameras;
  final AppVisualTheme themeSelection;
  final Future<void> Function(AppVisualTheme theme) onThemeChanged;

  @override
  State<MainShellScreen> createState() => _MainShellScreenState();
}

class _MainShellScreenState extends State<MainShellScreen> {
  int _currentIndex = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: [
          HomeDashboardScreen(
            cameras: widget.cameras,
            onGoSupport: () => setState(() => _currentIndex = 1),
          ),
          SupportHubScreen(cameras: widget.cameras),
          const FindHelpScreen(),
          MascotBuddyScreen(
            cameras: widget.cameras,
            themeSelection: widget.themeSelection,
            onThemeChanged: widget.onThemeChanged,
            onGoHome: () => setState(() => _currentIndex = 0),
            onGoSupport: () => setState(() => _currentIndex = 1),
          ),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex,
        onDestinationSelected: (index) {
          setState(() {
            _currentIndex = index;
          });
        },
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.home_outlined),
            selectedIcon: Icon(Icons.home),
            label: 'Home',
          ),
          NavigationDestination(
            icon: Icon(Icons.support_agent_outlined),
            selectedIcon: Icon(Icons.support_agent),
            label: 'Support',
          ),
          NavigationDestination(
            icon: Icon(Icons.medical_services_outlined),
            selectedIcon: Icon(Icons.medical_services),
            label: 'Find Help',
          ),
          NavigationDestination(
            icon: Icon(Icons.smart_toy_outlined),
            selectedIcon: Icon(Icons.smart_toy),
            label: 'Buddy',
          ),
        ],
      ),
    );
  }
}
