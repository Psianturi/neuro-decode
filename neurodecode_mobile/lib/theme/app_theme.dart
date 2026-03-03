import 'package:flutter/material.dart';

class NeuroColors {
  static const Color background = Color(0xFF0D2428);
  static const Color surface = Color(0xFF12353A);
  static const Color surfaceVariant = Color(0xFF1A464D);
  static const Color primary = Color(0xFF3ED0C5);
  static const Color secondary = Color(0xFF7BC9E8);
  static const Color textPrimary = Color(0xFFEAF4F4);
  static const Color textSecondary = Color(0xFFA9C2C5);
}

class AppTheme {
  static ThemeData get darkTheme {
    final scheme = const ColorScheme.dark(
      primary: NeuroColors.primary,
      secondary: NeuroColors.secondary,
      surface: NeuroColors.surface,
      onSurface: NeuroColors.textPrimary,
      onPrimary: Color(0xFF052526),
      onSecondary: Color(0xFF10262B),
      error: Color(0xFFFF7D7D),
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: scheme,
      scaffoldBackgroundColor: NeuroColors.background,
      appBarTheme: const AppBarTheme(
        backgroundColor: NeuroColors.background,
        foregroundColor: NeuroColors.textPrimary,
        centerTitle: false,
      ),
      cardTheme: CardTheme(
        color: NeuroColors.surface,
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: NeuroColors.primary,
          foregroundColor: scheme.onPrimary,
          minimumSize: const Size.fromHeight(56),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
          textStyle: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: NeuroColors.secondary,
          side: const BorderSide(color: NeuroColors.secondary, width: 1.4),
          minimumSize: const Size.fromHeight(52),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
        ),
      ),
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return NeuroColors.primary;
          }
          return NeuroColors.textSecondary;
        }),
        trackColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return NeuroColors.primary.withValues(alpha: 0.4);
          }
          return NeuroColors.surfaceVariant;
        }),
      ),
      textTheme: const TextTheme(
        headlineSmall: TextStyle(
          fontSize: 28,
          fontWeight: FontWeight.w800,
          color: NeuroColors.textPrimary,
          letterSpacing: -0.4,
        ),
        titleLarge: TextStyle(
          fontSize: 24,
          fontWeight: FontWeight.w700,
          color: NeuroColors.textPrimary,
        ),
        titleMedium: TextStyle(
          fontSize: 20,
          fontWeight: FontWeight.w700,
          color: NeuroColors.textPrimary,
        ),
        bodyLarge: TextStyle(
          fontSize: 17,
          color: NeuroColors.textPrimary,
        ),
        bodyMedium: TextStyle(
          fontSize: 15,
          color: NeuroColors.textSecondary,
        ),
      ),
    );
  }
}
