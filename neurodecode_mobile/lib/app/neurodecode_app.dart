import 'package:flutter/material.dart';
import 'package:camera/camera.dart';

import '../config/app_theme_store.dart';
import '../features/shell/main_shell_screen.dart';
import '../theme/app_theme.dart';

class NeuroDecodeApp extends StatefulWidget {
  const NeuroDecodeApp({
    super.key,
    required this.cameras,
  });

  final List<CameraDescription> cameras;

  @override
  State<NeuroDecodeApp> createState() => _NeuroDecodeAppState();
}

class _NeuroDecodeAppState extends State<NeuroDecodeApp> {
  final AppThemeStore _themeStore = AppThemeStore();
  AppVisualTheme _themeSelection = AppVisualTheme.light;
  bool _themeLoaded = false;

  @override
  void initState() {
    super.initState();
    _loadTheme();
  }

  Future<void> _loadTheme() async {
    final theme = await _themeStore.getTheme();
    if (!mounted) {
      return;
    }
    setState(() {
      _themeSelection = theme;
      _themeLoaded = true;
    });
  }

  Future<void> _setTheme(AppVisualTheme nextTheme) async {
    if (_themeSelection == nextTheme) {
      return;
    }
    await _themeStore.setTheme(nextTheme);
    if (!mounted) {
      return;
    }
    setState(() {
      _themeSelection = nextTheme;
    });
  }

  @override
  Widget build(BuildContext context) {
    final activeTheme = AppTheme.forSelection(_themeSelection);

    return MaterialApp(
      title: 'AnakUnggul',
      debugShowCheckedModeBanner: false,
      theme: activeTheme,
      darkTheme: AppTheme.darkGreenTheme,
      themeMode: _themeSelection == AppVisualTheme.dark
          ? ThemeMode.dark
          : ThemeMode.light,
      home: !_themeLoaded
          ? const SizedBox.shrink()
          : MainShellScreen(
              cameras: widget.cameras,
              themeSelection: _themeSelection,
              onThemeChanged: _setTheme,
            ),
    );
  }
}
