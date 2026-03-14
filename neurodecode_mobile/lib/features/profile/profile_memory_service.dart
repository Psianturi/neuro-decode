import 'dart:convert';
import 'dart:io';

import '../../config/app_config.dart';
import '../../config/app_identity_store.dart';

class ProfileRecord {
  const ProfileRecord({
    required this.profileId,
    required this.name,
    required this.childName,
    required this.caregiverName,
    required this.notes,
    required this.generatedSummary,
    required this.triggerTags,
    required this.calmingTags,
    required this.communicationTags,
    required this.raw,
  });

  final String profileId;
  final String name;
  final String childName;
  final String caregiverName;
  final String notes;
  final String generatedSummary;
  final List<String> triggerTags;
  final List<String> calmingTags;
  final List<String> communicationTags;
  final Map<String, dynamic> raw;

  factory ProfileRecord.fromJson(String profileId, Map<String, dynamic> json) {
    String pick(List<String> keys) {
      for (final key in keys) {
        final rawValue = json[key];
        if (rawValue == null) {
          continue;
        }
        final value = rawValue.toString().trim();
        if (value.isNotEmpty) {
          return value;
        }
      }
      return '';
    }

    List<String> pickList(List<String> keys) {
      for (final key in keys) {
        final rawValue = json[key];
        if (rawValue is List) {
          final values = rawValue
              .map((item) => item.toString().trim())
              .where((item) => item.isNotEmpty)
              .toList();
          if (values.isNotEmpty) {
            return values;
          }
        }
      }
      return const <String>[];
    }

    return ProfileRecord(
      profileId: profileId,
      name: pick(const ['name', 'profile_name', 'display_name']),
      childName: pick(const ['child_name', 'childName']),
      caregiverName: pick(const ['caregiver_name', 'caregiverName']),
      notes: pick(const ['notes', 'support_notes', 'summary']),
      generatedSummary: pick(const ['generated_summary', 'profile_summary']),
      triggerTags: pickList(const ['trigger_tags', 'triggers']),
      calmingTags: pickList(const ['calming_tags', 'calming_supports']),
      communicationTags:
          pickList(const ['communication_tags', 'communication_preferences']),
      raw: Map<String, dynamic>.from(json),
    );
  }
}

class ProfileMemoryItem {
  const ProfileMemoryItem({
    required this.category,
    required this.note,
    required this.confidence,
    required this.updatedAtUtc,
    required this.active,
  });

  final String category;
  final String note;
  final String confidence;
  final String updatedAtUtc;
  final bool active;

  factory ProfileMemoryItem.fromJson(Map<String, dynamic> json) {
    String pick(List<String> keys, [String fallback = '']) {
      for (final key in keys) {
        final rawValue = json[key];
        if (rawValue == null) {
          continue;
        }
        final value = rawValue.toString().trim();
        if (value.isNotEmpty) {
          return value;
        }
      }
      return fallback;
    }

    final activeValue = json['active'];
    final isActive = activeValue is bool
        ? activeValue
        : activeValue?.toString().toLowerCase() != 'false';

    return ProfileMemoryItem(
      category: pick(const ['category', 'type'], 'general'),
      note: pick(const ['note', 'text', 'content', 'summary'], '-'),
      confidence: pick(const ['confidence'], 'medium'),
      updatedAtUtc:
          pick(const ['updated_at_utc', 'timestamp_utc', 'created_at_utc']),
      active: isActive,
    );
  }
}

class ProfileMemoryContext {
  const ProfileMemoryContext({
    required this.profileFound,
    required this.memoryItemCount,
    required this.recentSessionCount,
    required this.context,
  });

  final bool profileFound;
  final int memoryItemCount;
  final int recentSessionCount;
  final String context;

  factory ProfileMemoryContext.fromJson(Map<String, dynamic> json) {
    int parseInt(dynamic value) {
      if (value is int) {
        return value;
      }
      if (value is num) {
        return value.toInt();
      }
      return int.tryParse(value?.toString() ?? '') ?? 0;
    }

    final profileFoundValue = json['profile_found'];
    return ProfileMemoryContext(
      profileFound: profileFoundValue is bool
          ? profileFoundValue
          : profileFoundValue?.toString().toLowerCase() == 'true',
      memoryItemCount: parseInt(json['memory_item_count']),
      recentSessionCount: parseInt(json['recent_session_count']),
      context: (json['context'] ?? '').toString().trim(),
    );
  }
}

class ProfileMemoryService {
  ProfileMemoryService({AppIdentityStore? identityStore})
      : _identityStore = identityStore ?? AppIdentityStore();

  final AppIdentityStore _identityStore;

  Future<Uri> _buildUri(String path) async {
    final userId = await _identityStore.getOrCreateUserId();
    return Uri.parse('https://${AppConfig.backendUrl}$path').replace(
      queryParameters: {
        'user_id': userId,
      },
    );
  }

  Future<Map<String, dynamic>> _sendJson({
    required String method,
    required Uri uri,
    Map<String, dynamic>? payload,
  }) async {
    final client = HttpClient();
    client.connectionTimeout = const Duration(seconds: 10);

    try {
      final request = await client.openUrl(method, uri);
      request.headers.contentType = ContentType.json;
      if (payload != null) {
        request.write(jsonEncode(payload));
      }

      final response = await request.close();
      final body = await response.transform(utf8.decoder).join();
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw HttpException(
          'Request failed (${response.statusCode})',
          uri: uri,
        );
      }

      final decoded = jsonDecode(body);
      if (decoded is! Map<String, dynamic>) {
        throw const FormatException('Invalid JSON object');
      }
      return decoded;
    } finally {
      client.close(force: true);
    }
  }

  Future<ProfileRecord?> fetchProfile(String profileId) async {
    final decoded = await _sendJson(
      method: 'GET',
      uri: await _buildUri('/profiles/$profileId'),
    );

    if ((decoded['status'] ?? '').toString() == 'empty') {
      return null;
    }

    final profile = decoded['profile'];
    if (profile is! Map<String, dynamic>) {
      return null;
    }
    return ProfileRecord.fromJson(profileId, profile);
  }

  Future<ProfileRecord> saveProfile({
    required String profileId,
    required String name,
    required String childName,
    required String caregiverName,
    required String notes,
    required String generatedSummary,
    required List<String> triggerTags,
    required List<String> calmingTags,
    required List<String> communicationTags,
  }) async {
    final payload = <String, dynamic>{
      'name': name.trim(),
      'child_name': childName.trim(),
      'caregiver_name': caregiverName.trim(),
      'notes': notes.trim(),
      'generated_summary': generatedSummary.trim(),
      'trigger_tags': triggerTags,
      'calming_tags': calmingTags,
      'communication_tags': communicationTags,
    };
    final decoded = await _sendJson(
      method: 'PUT',
      uri: await _buildUri('/profiles/$profileId'),
      payload: payload,
    );

    final profile = decoded['profile'];
    if (profile is! Map<String, dynamic>) {
      throw const FormatException('Profile response missing profile data');
    }
    return ProfileRecord.fromJson(profileId, profile);
  }

  Future<List<ProfileMemoryItem>> fetchMemory(String profileId) async {
    final decoded = await _sendJson(
      method: 'GET',
      uri: await _buildUri('/profiles/$profileId/memory?limit=25'),
    );

    final items = decoded['items'];
    if (items is! List) {
      return const <ProfileMemoryItem>[];
    }

    return items
        .whereType<Map<String, dynamic>>()
        .map(ProfileMemoryItem.fromJson)
        .toList();
  }

  Future<void> addMemory({
    required String profileId,
    required String category,
    required String note,
    required String confidence,
  }) async {
    await _sendJson(
      method: 'POST',
      uri: await _buildUri('/profiles/$profileId/memory'),
      payload: {
        'category': category.trim(),
        'note': note.trim(),
        'confidence': confidence.trim(),
        'active': true,
      },
    );
  }

  Future<ProfileMemoryContext> fetchMemoryContext(String profileId) async {
    final decoded = await _sendJson(
      method: 'GET',
      uri: await _buildUri('/profiles/$profileId/memory-context'),
    );
    return ProfileMemoryContext.fromJson(decoded);
  }
}
