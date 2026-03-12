import 'dart:math';

import 'package:shared_preferences/shared_preferences.dart';

class AppIdentityStore {
  static const String _userIdKey = 'neurodecode_user_id';
  static const String _activeProfileIdKey = 'neurodecode_active_profile_id';

  Future<String> getOrCreateUserId() async {
    final prefs = await SharedPreferences.getInstance();
    final existing = prefs.getString(_userIdKey)?.trim();
    if (existing != null && existing.isNotEmpty) {
      return existing;
    }

    final generated = _generateUserId();
    await prefs.setString(_userIdKey, generated);
    return generated;
  }

  Future<String?> getActiveProfileId() async {
    final prefs = await SharedPreferences.getInstance();
    final existing = prefs.getString(_activeProfileIdKey)?.trim();
    if (existing == null || existing.isEmpty) {
      return null;
    }
    return existing;
  }

  Future<void> setActiveProfileId(String? profileId) async {
    final prefs = await SharedPreferences.getInstance();
    final trimmed = profileId?.trim();
    if (trimmed == null || trimmed.isEmpty) {
      await prefs.remove(_activeProfileIdKey);
      return;
    }
    await prefs.setString(_activeProfileIdKey, trimmed);
  }

  String _generateUserId() {
    final random = Random();
    final timestamp = DateTime.now().microsecondsSinceEpoch.toRadixString(16);
    final nonce = random.nextInt(1 << 32).toRadixString(16);
    return 'user-$timestamp-$nonce';
  }
}
