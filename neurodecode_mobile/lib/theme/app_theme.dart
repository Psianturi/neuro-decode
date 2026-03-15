import 'package:flutter/material.dart';

enum AppVisualTheme {
  light,
  dark,
  pink,
}

class NeuroColors {
  // Light (default) palette — adjusted for WCAG AA contrast.
  static const Color background = Color(0xFFF4F7FB);
  static const Color surface = Color(0xFFFFFFFF);
  static const Color surfaceVariant = Color(0xFFEAF1FA);
  static const Color primary = Color(0xFF4A90C8);
  static const Color primaryLight = Color(0xFF7FB2E4);
  static const Color secondary = Color(0xFF5BA8A2);
  static const Color textPrimary = Color(0xFF2C3E50);
  static const Color textSecondary = Color(0xFF546E7A);
  static const Color accent = Color(0xFF3B7DD8);

  // Soft pink palette.
  static const Color pinkBackground = Color(0xFFFFF6FA);
  static const Color pinkSurface = Color(0xFFFFFFFF);
  static const Color pinkSurfaceVariant = Color(0xFFFBE6EF);
  static const Color pinkPrimary = Color(0xFFE08FB1);
  static const Color pinkSecondary = Color(0xFFC98AA4);
  static const Color pinkTextPrimary = Color(0xFF4E4050);
  static const Color pinkTextSecondary = Color(0xFF7B6877);

  // Dark palette.
  static const Color darkBackground = Color(0xFF0E1726);
  static const Color darkSurface = Color(0xFF162234);
  static const Color darkSurfaceVariant = Color(0xFF23344B);
  static const Color darkPrimary = Color(0xFF79AEE8);
  static const Color darkSecondary = Color(0xFF66D1C8);
  static const Color darkTextPrimary = Color(0xFFF4F7FB);
  static const Color darkTextSecondary = Color(0xFFB1C0D1);

  // Standardised spacing.
  static const double spacingXs = 4;
  static const double spacingSm = 8;
  static const double spacingMd = 16;
  static const double spacingLg = 24;
  static const double spacingXl = 32;

  // Standardised radii.
  static const double radiusSm = 12;
  static const double radiusMd = 16;
  static const double radiusLg = 24;
  static const double radiusPill = 999;
}

class AppTheme {
  static ThemeData forSelection(AppVisualTheme selection) {
    switch (selection) {
      case AppVisualTheme.dark:
        return darkGreenTheme;
      case AppVisualTheme.pink:
        return softPinkTheme;
      case AppVisualTheme.light:
        return lightTheme;
    }
  }

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
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(NeuroColors.radiusMd)),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: NeuroColors.primary,
          foregroundColor: scheme.onPrimary,
          minimumSize: const Size.fromHeight(56),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(NeuroColors.radiusLg)),
          textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, letterSpacing: 0.3),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: NeuroColors.primary,
          side: const BorderSide(color: NeuroColors.primary, width: 1.4),
          minimumSize: const Size.fromHeight(48),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(NeuroColors.radiusLg)),
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
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: NeuroColors.surface,
        indicatorColor: NeuroColors.primary.withValues(alpha: 0.14),
        elevation: 2,
        shadowColor: Colors.black26,
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: NeuroColors.primary,
            );
          }
          return const TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w500,
            color: NeuroColors.textSecondary,
          );
        }),
        iconTheme: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const IconThemeData(color: NeuroColors.primary, size: 24);
          }
          return const IconThemeData(color: NeuroColors.textSecondary, size: 24);
        }),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: NeuroColors.surfaceVariant.withValues(alpha: 0.5),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(NeuroColors.radiusSm),
          borderSide: BorderSide(color: NeuroColors.surfaceVariant),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(NeuroColors.radiusSm),
          borderSide: BorderSide(color: NeuroColors.surfaceVariant),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(NeuroColors.radiusSm),
          borderSide: const BorderSide(color: NeuroColors.primary, width: 1.5),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
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
        titleSmall: TextStyle(
          fontSize: 16,
          fontWeight: FontWeight.w600,
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
        bodySmall: TextStyle(
          fontSize: 13,
          color: NeuroColors.textSecondary,
        ),
        labelLarge: TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w600,
          color: NeuroColors.textPrimary,
          letterSpacing: 0.3,
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
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(NeuroColors.radiusMd)),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: NeuroColors.darkPrimary,
          foregroundColor: scheme.onPrimary,
          minimumSize: const Size.fromHeight(56),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(NeuroColors.radiusLg)),
          textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, letterSpacing: 0.3),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: NeuroColors.darkSecondary,
          side: const BorderSide(color: NeuroColors.darkSecondary, width: 1.4),
          minimumSize: const Size.fromHeight(48),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(NeuroColors.radiusLg)),
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
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: NeuroColors.darkSurface,
        indicatorColor: NeuroColors.darkPrimary.withValues(alpha: 0.14),
        elevation: 2,
        shadowColor: Colors.black54,
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: NeuroColors.darkPrimary,
            );
          }
          return const TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w500,
            color: NeuroColors.darkTextSecondary,
          );
        }),
        iconTheme: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const IconThemeData(color: NeuroColors.darkPrimary, size: 24);
          }
          return const IconThemeData(color: NeuroColors.darkTextSecondary, size: 24);
        }),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: NeuroColors.darkSurfaceVariant.withValues(alpha: 0.5),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(NeuroColors.radiusSm),
          borderSide: BorderSide(color: NeuroColors.darkSurfaceVariant),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(NeuroColors.radiusSm),
          borderSide: BorderSide(color: NeuroColors.darkSurfaceVariant),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(NeuroColors.radiusSm),
          borderSide: const BorderSide(color: NeuroColors.darkPrimary, width: 1.5),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
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
        titleSmall: TextStyle(
          fontSize: 16,
          fontWeight: FontWeight.w600,
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
        bodySmall: TextStyle(
          fontSize: 13,
          color: NeuroColors.darkTextSecondary,
        ),
        labelLarge: TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w600,
          color: NeuroColors.darkTextPrimary,
          letterSpacing: 0.3,
        ),
      ),
    );
  }

  static ThemeData get softPinkTheme {
    final scheme = const ColorScheme.light(
      primary: NeuroColors.pinkPrimary,
      secondary: NeuroColors.pinkSecondary,
      surface: NeuroColors.pinkSurface,
      onSurface: NeuroColors.pinkTextPrimary,
      onPrimary: Colors.white,
      onSecondary: Colors.white,
      error: Color(0xFFD35353),
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      colorScheme: scheme,
      scaffoldBackgroundColor: NeuroColors.pinkBackground,
      appBarTheme: const AppBarTheme(
        backgroundColor: NeuroColors.pinkBackground,
        foregroundColor: NeuroColors.pinkTextPrimary,
        centerTitle: false,
      ),
      cardTheme: CardTheme(
        color: NeuroColors.pinkSurface,
        elevation: 1,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(NeuroColors.radiusMd),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: NeuroColors.pinkPrimary,
          foregroundColor: scheme.onPrimary,
          minimumSize: const Size.fromHeight(56),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(NeuroColors.radiusLg),
          ),
          textStyle: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w700,
            letterSpacing: 0.3,
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: NeuroColors.pinkPrimary,
          side: const BorderSide(color: NeuroColors.pinkPrimary, width: 1.4),
          minimumSize: const Size.fromHeight(48),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(NeuroColors.radiusLg),
          ),
        ),
      ),
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return NeuroColors.pinkPrimary;
          }
          return NeuroColors.pinkTextSecondary;
        }),
        trackColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return NeuroColors.pinkPrimary.withValues(alpha: 0.4);
          }
          return NeuroColors.pinkSurfaceVariant;
        }),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: NeuroColors.pinkSurface,
        indicatorColor: NeuroColors.pinkPrimary.withValues(alpha: 0.16),
        elevation: 2,
        shadowColor: Colors.black12,
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: NeuroColors.pinkPrimary,
            );
          }
          return const TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w500,
            color: NeuroColors.pinkTextSecondary,
          );
        }),
        iconTheme: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const IconThemeData(
              color: NeuroColors.pinkPrimary,
              size: 24,
            );
          }
          return const IconThemeData(
            color: NeuroColors.pinkTextSecondary,
            size: 24,
          );
        }),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: NeuroColors.pinkSurfaceVariant.withValues(alpha: 0.55),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(NeuroColors.radiusSm),
          borderSide: const BorderSide(color: NeuroColors.pinkSurfaceVariant),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(NeuroColors.radiusSm),
          borderSide: const BorderSide(color: NeuroColors.pinkSurfaceVariant),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(NeuroColors.radiusSm),
          borderSide: const BorderSide(
            color: NeuroColors.pinkPrimary,
            width: 1.5,
          ),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      ),
      textTheme: const TextTheme(
        headlineSmall: TextStyle(
          fontSize: 28,
          fontWeight: FontWeight.w800,
          color: NeuroColors.pinkTextPrimary,
          letterSpacing: -0.4,
        ),
        titleLarge: TextStyle(
          fontSize: 24,
          fontWeight: FontWeight.w700,
          color: NeuroColors.pinkTextPrimary,
        ),
        titleMedium: TextStyle(
          fontSize: 20,
          fontWeight: FontWeight.w700,
          color: NeuroColors.pinkTextPrimary,
        ),
        titleSmall: TextStyle(
          fontSize: 16,
          fontWeight: FontWeight.w600,
          color: NeuroColors.pinkTextPrimary,
        ),
        bodyLarge: TextStyle(
          fontSize: 17,
          color: NeuroColors.pinkTextPrimary,
        ),
        bodyMedium: TextStyle(
          fontSize: 15,
          color: NeuroColors.pinkTextSecondary,
        ),
        bodySmall: TextStyle(
          fontSize: 13,
          color: NeuroColors.pinkTextSecondary,
        ),
        labelLarge: TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w600,
          color: NeuroColors.pinkTextPrimary,
          letterSpacing: 0.3,
        ),
      ),
    );
  }
}
