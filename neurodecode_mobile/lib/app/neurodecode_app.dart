import 'package:flutter/material.dart';
import 'package:camera/camera.dart';

import '../features/shell/main_shell_screen.dart';
import '../theme/app_theme.dart';

class NeuroDecodeApp extends StatelessWidget {
  const NeuroDecodeApp({
    super.key,
    required this.cameras,
  });

  final List<CameraDescription> cameras;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'NeuroDecode AI',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkGreenTheme,
      themeMode: ThemeMode.light,
      home: MainShellScreen(cameras: cameras),
    );
  }
}
