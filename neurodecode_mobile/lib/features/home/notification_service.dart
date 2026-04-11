import 'dart:convert';
import 'dart:io';

import '../../config/app_config.dart';
import '../../config/app_identity_store.dart';

class NotificationItem {
  const NotificationItem({
    required this.notificationId,
    required this.title,
    required this.message,
    required this.severity,
    required this.status,
    required this.createdAtUtc,
    required this.profileId,
    required this.ruleId,
  });

  final String notificationId;
  final String title;
  final String message;
  final String severity;
  final String status;
  final String createdAtUtc;
  final String profileId;
  final String ruleId;

  bool get isUnread => status.toLowerCase() == 'unread';

  factory NotificationItem.fromJson(Map<String, dynamic> json) {
    String pick(String key, [String fallback = '']) {
      final raw = json[key];
      if (raw == null) {
        return fallback;
      }
      final value = raw.toString().trim();
      return value.isEmpty ? fallback : value;
    }

    return NotificationItem(
      notificationId: pick('notification_id'),
      title: pick('title', 'AnakUnggul notice'),
      message: pick('message', '-'),
      severity: pick('severity', 'info'),
      status: pick('status', 'unread'),
      createdAtUtc: pick('created_at_utc'),
      profileId: pick('profile_id'),
      ruleId: pick('rule_id'),
    );
  }
}

class NotificationService {
  NotificationService({AppIdentityStore? identityStore})
      : _identityStore = identityStore ?? AppIdentityStore();

  final AppIdentityStore _identityStore;

  Future<Uri> _buildUri(
    String path, {
    Map<String, String>? extraQuery,
  }) async {
    final userId = await _identityStore.getOrCreateUserId();
    final profileId = await _identityStore.getActiveProfileId();

    final query = <String, String>{
      'user_id': userId,
      if (profileId != null && profileId.isNotEmpty) 'profile_id': profileId,
      ...?extraQuery,
    };

    return Uri.parse('https://${AppConfig.backendUrl}$path').replace(
      queryParameters: query,
    );
  }

  Future<Map<String, dynamic>> _sendJson({
    required String method,
    required Uri uri,
  }) async {
    final client = HttpClient();
    client.connectionTimeout = const Duration(seconds: 10);

    try {
      final request = await client.openUrl(method, uri);
      request.headers.contentType = ContentType.json;

      final response = await request.close();
      final body = await response.transform(utf8.decoder).join();

      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw HttpException('Request failed (${response.statusCode})',
            uri: uri);
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

  Future<List<NotificationItem>> fetchAll({
    String? status,
    int limit = 30,
  }) async {
    final decoded = await _sendJson(
      method: 'GET',
      uri: await _buildUri(
        '/notifications',
        extraQuery: {
          'limit': '$limit',
          if (status != null && status.trim().isNotEmpty) 'status': status,
        },
      ),
    );

    final itemsRaw = decoded['items'];
    if (itemsRaw is! List) {
      return const <NotificationItem>[];
    }

    final out = <NotificationItem>[];
    for (final item in itemsRaw) {
      if (item is Map<String, dynamic>) {
        out.add(NotificationItem.fromJson(item));
      }
    }
    return out;
  }

  Future<void> markRead(String notificationId) async {
    if (notificationId.trim().isEmpty) {
      return;
    }
    await _sendJson(
      method: 'POST',
      uri: await _buildUri('/notifications/$notificationId/read'),
    );
  }
}
