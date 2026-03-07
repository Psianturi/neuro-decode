import 'package:flutter/material.dart';

class NeuroColors {
  // Light (default) palette inspired by Buddy page.
  static const Color background = Color(0xFFF4F7FB);
  static const Color surface = Color(0xFFFFFFFF);
  static const Color surfaceVariant = Color(0xFFEAF1FA);
  static const Color primary = Color(0xFF7FB2E4);
  static const Color secondary = Color(0xFF9BCBC7);
  static const Color textPrimary = Color(0xFF2C3E50);
  static const Color textSecondary = Color(0xFF637C90);

  // Optional green dark palette for future user setting.
  static const Color darkBackground = Color(0xFF0D2428);
  static const Color darkSurface = Color(0xFF12353A);
  static const Color darkSurfaceVariant = Color(0xFF1A464D);
  static const Color darkPrimary = Color(0xFF3ED0C5);
  static const Color darkSecondary = Color(0xFF7BC9E8);
  static const Color darkTextPrimary = Color(0xFFEAF4F4);
  static const Color darkTextSecondary = Color(0xFFA9C2C5);
}

class AppTheme {
  static ThemeData get lightTheme {
    final scheme = const ColorScheme.light(
      primary: NeuroColors.primary,
      secondary: NeuroColors.secondary,
      surface: NeuroColors.surface,
      onSurface: NeuroColors.textPrimary,
      onPrimary: Colors.white,
      onSecondary: Color(0xFF1A3044),
      error: Color(0xFFD35353),
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      colorScheme: scheme,
      scaffoldBackgroundColor: NeuroColors.background,
      appBarTheme: const AppBarTheme(
        backgroundColor: NeuroColors.background,
        foregroundColor: NeuroColors.textPrimary,
        centerTitle: false,
      ),
      cardTheme: CardTheme(
        color: NeuroColors.surface,
        elevation: 1,
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
          foregroundColor: NeuroColors.primary,
          side: const BorderSide(color: NeuroColors.primary, width: 1.4),
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
            return NeuroColors.primary.withValues(alpha: 0.45);
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

  static ThemeData get darkGreenTheme {
    final scheme = const ColorScheme.dark(
      primary: NeuroColors.darkPrimary,
      secondary: NeuroColors.darkSecondary,
      surface: NeuroColors.darkSurface,
      onSurface: NeuroColors.darkTextPrimary,
      onPrimary: Color(0xFF052526),
      onSecondary: Color(0xFF10262B),
      error: Color(0xFFFF7D7D),
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: scheme,
      scaffoldBackgroundColor: NeuroColors.darkBackground,
      appBarTheme: const AppBarTheme(
        backgroundColor: NeuroColors.darkBackground,
        foregroundColor: NeuroColors.darkTextPrimary,
        centerTitle: false,
      ),
      cardTheme: CardTheme(
        color: NeuroColors.darkSurface,
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: NeuroColors.darkPrimary,
          foregroundColor: scheme.onPrimary,
          minimumSize: const Size.fromHeight(56),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
          textStyle: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: NeuroColors.darkSecondary,
          side: const BorderSide(color: NeuroColors.darkSecondary, width: 1.4),
          minimumSize: const Size.fromHeight(52),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
        ),
      ),
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return NeuroColors.darkPrimary;
          }
          return NeuroColors.darkTextSecondary;
        }),
        trackColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return NeuroColors.darkPrimary.withValues(alpha: 0.4);
          }
          return NeuroColors.darkSurfaceVariant;
        }),
      ),
      textTheme: const TextTheme(
        headlineSmall: TextStyle(
          fontSize: 28,
          fontWeight: FontWeight.w800,
          color: NeuroColors.darkTextPrimary,
          letterSpacing: -0.4,
        ),
        titleLarge: TextStyle(
          fontSize: 24,
          fontWeight: FontWeight.w700,
          color: NeuroColors.darkTextPrimary,
        ),
        titleMedium: TextStyle(
          fontSize: 20,
          fontWeight: FontWeight.w700,
          color: NeuroColors.darkTextPrimary,
        ),
        bodyLarge: TextStyle(
          fontSize: 17,
          color: NeuroColors.darkTextPrimary,
        ),
        bodyMedium: TextStyle(
          fontSize: 15,
          color: NeuroColors.darkTextSecondary,
        ),
      ),
    );
  }
}
