import 'dart:math';

import 'package:shared_preferences/shared_preferences.dart';

class AppIdentityStore {
  static const String _userIdKey = 'neurodecode_user_id';
  static const String _activeProfileIdKey = 'neurodecode_active_profile_id';
  static const String _recentProfileIdsKey = 'neurodecode_recent_profile_ids';
  static const String _legacyClaimStatusKey = 'neurodecode_legacy_claim_status';
  static const int _maxRecentProfiles = 12;

  /// Legacy, pre-Firebase-Auth local identifier. Kept only so a device that
  /// already has one can migrate its existing backend data to the new
  /// verified Firebase uid once (see AuthIdentity.attemptLegacyClaimIfNeeded).
  /// Not used for new backend calls — those are authenticated by ID token.
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

  /// Same as [getOrCreateUserId] but never fabricates a new id. A fresh
  /// install has no legacy data, so returning null here (rather than
  /// creating an id that was never real) is what lets the migration flow
  /// tell "nothing to migrate" apart from "haven't tried yet".
  Future<String?> readExistingUserId() async {
    final prefs = await SharedPreferences.getInstance();
    final existing = prefs.getString(_userIdKey)?.trim();
    return (existing != null && existing.isNotEmpty) ? existing : null;
  }

  Future<String?> getLegacyClaimStatus() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_legacyClaimStatusKey);
  }

  /// Persist a terminal claim-legacy outcome ('complete' | 'conflict' |
  /// 'expired') only — never called for a transient failure, so a retry is
  /// always attempted again on the next app launch until one of those lands.
  Future<void> setLegacyClaimStatus(String status) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_legacyClaimStatusKey, status);
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
    await _rememberRecentProfileId(trimmed);
  }

  Future<List<String>> listRecentProfileIds() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getStringList(_recentProfileIdsKey) ?? const <String>[];
    return raw
        .map((item) => item.trim())
        .where((item) => item.isNotEmpty)
        .toList();
  }

  Future<void> removeRecentProfileId(String profileId) async {
    final prefs = await SharedPreferences.getInstance();
    final target = profileId.trim();
    if (target.isEmpty) {
      return;
    }

    final recent = await listRecentProfileIds();
    recent.removeWhere((item) => item == target);
    await prefs.setStringList(_recentProfileIdsKey, recent);

    final active = await getActiveProfileId();
    if (active == target) {
      await prefs.remove(_activeProfileIdKey);
    }
  }

  Future<void> _rememberRecentProfileId(String profileId) async {
    final prefs = await SharedPreferences.getInstance();
    final recent = await listRecentProfileIds();
    recent.removeWhere((item) => item == profileId);
    recent.insert(0, profileId);
    if (recent.length > _maxRecentProfiles) {
      recent.removeRange(_maxRecentProfiles, recent.length);
    }
    await prefs.setStringList(_recentProfileIdsKey, recent);
  }

  String _generateUserId() {
    final random = Random();
    final timestamp = DateTime.now().microsecondsSinceEpoch.toRadixString(16);
    final nonce = random.nextInt(1 << 32).toRadixString(16);
    return 'user-$timestamp-$nonce';
  }
}
