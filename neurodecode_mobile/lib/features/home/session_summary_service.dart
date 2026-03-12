import 'dart:convert';
import 'dart:io';

import '../../config/app_config.dart';
import '../../config/app_identity_store.dart';

class SessionSummary {
  const SessionSummary({
    required this.timestampUtc,
    required this.durationMinutes,
    required this.closeReason,
    required this.title,
    required this.triggersVisual,
    required this.triggersAudio,
    required this.agentActions,
    required this.followUp,
    required this.safetyNote,
  });

  final String timestampUtc;
  final int durationMinutes;
  final String closeReason;
  final String title;
  final String triggersVisual;
  final String triggersAudio;
  final String agentActions;
  final String followUp;
  final String safetyNote;

  String get closeReasonLabel {
    switch (closeReason) {
      case 'completed':
        return 'Completed';
      case 'client_close':
        return 'Ended by caregiver';
      case 'client_disconnect':
        return 'Disconnected';
      case 'idle_timeout':
        return 'Timed out';
      case 'error':
        return 'Error';
      case 'unknown':
      case '-':
        return 'Completed';
      default:
        return closeReason.replaceAll('_', ' ');
    }
  }

  factory SessionSummary.fromJson(Map<String, dynamic> json) {
    final structured =
        (json['structured'] as Map<String, dynamic>? ?? <String, dynamic>{});

    int parseInt(dynamic value, int fallback) {
      if (value is int) {
        return value;
      }
      if (value is num) {
        return value.toInt();
      }
      if (value is String) {
        return int.tryParse(value) ?? fallback;
      }
      return fallback;
    }

    String pick(Map<String, dynamic> source, String key, String fallback) {
      final raw = source[key];
      if (raw == null) {
        return fallback;
      }
      final text = raw.toString().trim();
      return text.isEmpty ? fallback : text;
    }

    return SessionSummary(
      timestampUtc: pick(json, 'timestamp_utc', '-'),
      durationMinutes: parseInt(json['duration_minutes'], 0),
      closeReason: pick(json, 'close_reason', '-'),
      title: pick(structured, 'title', 'Session Summary'),
      triggersVisual: pick(structured, 'triggers_visual', '-'),
      triggersAudio: pick(structured, 'triggers_audio', '-'),
      agentActions: pick(structured, 'agent_actions', '-'),
      followUp: pick(structured, 'follow_up', '-'),
      safetyNote: pick(structured, 'safety_note', '-'),
    );
  }
}

class SessionSummaryService {
  SessionSummaryService({AppIdentityStore? identityStore})
      : _identityStore = identityStore ?? AppIdentityStore();

  final AppIdentityStore _identityStore;

  Future<Uri> _buildUri(String path) async {
    final userId = await _identityStore.getOrCreateUserId();
    final profileId = await _identityStore.getActiveProfileId();
    return Uri.parse('https://${AppConfig.backendUrl}$path').replace(
      queryParameters: {
        'user_id': userId,
        if (profileId != null && profileId.isNotEmpty) 'profile_id': profileId,
      },
    );
  }

  Future<Map<String, dynamic>> _getJson(Uri uri) async {
    final client = HttpClient();
    client.connectionTimeout = const Duration(seconds: 8);

    try {
      final request = await client.getUrl(uri);
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

  Future<SessionSummary?> fetchLatest() async {
    final decoded = await _getJson(await _buildUri('/sessions/latest'));

    final status = (decoded['status'] ?? '').toString();
    if (status == 'empty') {
      return null;
    }

    final session = decoded['session'];
    if (session is! Map<String, dynamic>) {
      return null;
    }

    return SessionSummary.fromJson(session);
  }

  Future<List<SessionSummary>> fetchAll() async {
    final decoded = await _getJson(await _buildUri('/sessions'));

    final sessionsRaw = decoded['sessions'];
    if (sessionsRaw is! List) {
      return const <SessionSummary>[];
    }

    final out = <SessionSummary>[];
    for (final item in sessionsRaw) {
      if (item is Map<String, dynamic>) {
        out.add(SessionSummary.fromJson(item));
      }
    }
    return out;
  }
}
