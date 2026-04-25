import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

/// A single daily behavioral check-in entry recorded by the caregiver.
class DailyCheckin {
  const DailyCheckin({
    required this.id,
    required this.profileId,
    required this.chips,
    required this.notes,
    required this.timestamp,
  });

  final String id;
  final String profileId;
  final List<String> chips;
  final String notes;
  final DateTime timestamp;

  Map<String, dynamic> toJson() => {
        'id': id,
        'profileId': profileId,
        'chips': chips,
        'notes': notes,
        'timestamp': timestamp.toIso8601String(),
      };

  factory DailyCheckin.fromJson(Map<String, dynamic> json) => DailyCheckin(
        id: json['id'] as String,
        profileId: json['profileId'] as String,
        chips: List<String>.from(json['chips'] as List),
        notes: json['notes'] as String,
        timestamp: DateTime.parse(json['timestamp'] as String),
      );
}

/// Persists daily check-ins locally via SharedPreferences (Phase 1).
///
/// Storage key pattern: `checkins_<profileId>`
/// Each key holds a JSON-encoded list of [DailyCheckin] objects.
class DailyCheckinService {
  static const int _maxPerProfile = 90; // ~3 months of daily entries

  String _key(String profileId) => 'checkins_$profileId';

  /// Save a new check-in for [profileId] with the given [chips] and [notes].
  Future<DailyCheckin> saveCheckin({
    required String profileId,
    required List<String> chips,
    required String notes,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    final existing = _loadFromPrefs(prefs, profileId);

    final entry = DailyCheckin(
      id: '${profileId}_${DateTime.now().millisecondsSinceEpoch}',
      profileId: profileId,
      chips: chips,
      notes: notes,
      timestamp: DateTime.now(),
    );

    final updated = [entry, ...existing];
    // Trim to avoid unbounded growth
    final trimmed = updated.length > _maxPerProfile
        ? updated.sublist(0, _maxPerProfile)
        : updated;

    await prefs.setString(
      _key(profileId),
      jsonEncode(trimmed.map((e) => e.toJson()).toList()),
    );

    return entry;
  }

  /// Load all check-ins for [profileId], newest first.
  Future<List<DailyCheckin>> loadCheckins(String profileId) async {
    final prefs = await SharedPreferences.getInstance();
    return _loadFromPrefs(prefs, profileId);
  }

  List<DailyCheckin> _loadFromPrefs(
      SharedPreferences prefs, String profileId) {
    final raw = prefs.getString(_key(profileId));
    if (raw == null || raw.isEmpty) return const [];
    try {
      final list = jsonDecode(raw) as List;
      return list
          .map((e) => DailyCheckin.fromJson(e as Map<String, dynamic>))
          .toList();
    } catch (_) {
      return const [];
    }
  }
}

/// Maps a check-in chip label to the most appropriate Profile Memory category.
///
/// Categories that match [ProfileMemoryScreen._memoryCategories]:
/// `trigger`, `calming`, `routine`, `safety`, `preference`.
String chipToMemoryCategory(String chip) {
  switch (chip) {
    case 'Sensory overload':
    case 'Mild meltdown':
    case 'New trigger noticed':
      return 'trigger';
    case 'Hard to sleep':
    case 'Big transition difficulty':
      return 'routine';
    case 'Everything calm':
      return 'preference';
    default:
      return 'trigger';
  }
}

/// Returns true when the chip describes a challenging event that warrants
/// surfacing the "Save to Profile Memory?" suggestion dialog.
bool chipSuggestsMemory(String chip) =>
    chip == 'Sensory overload' ||
    chip == 'Mild meltdown' ||
    chip == 'New trigger noticed' ||
    chip == 'Big transition difficulty';
