import 'package:shared_preferences/shared_preferences.dart';

import '../theme/app_theme.dart';

class AppThemeStore {
  static const String _themeKey = 'neurodecode_visual_theme';

  Future<AppVisualTheme> getTheme() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_themeKey)?.trim();
    return AppVisualTheme.values.firstWhere(
      (value) => value.name == raw,
      orElse: () => AppVisualTheme.light,
    );
  }

  Future<void> setTheme(AppVisualTheme theme) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_themeKey, theme.name);
  }
}