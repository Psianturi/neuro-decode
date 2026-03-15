import 'dart:convert';
import 'dart:io';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';

import '../../config/app_config.dart';
import '../../config/app_identity_store.dart';

class PushRegistrationService {
  PushRegistrationService({AppIdentityStore? identityStore})
      : _identityStore = identityStore ?? AppIdentityStore();

  final AppIdentityStore _identityStore;

  Future<void> registerCurrentDeviceToken() async {
    try {
      await Firebase.initializeApp();
    } catch (_) {
      // Firebase is not configured for this build/runtime.
      return;
    }

    try {
      await FirebaseMessaging.instance.requestPermission();
    } catch (_) {
      // Non-blocking: token may still be available on some platforms.
    }

    String? token;
    try {
      token = await FirebaseMessaging.instance.getToken();
    } catch (_) {
      return;
    }
    final trimmedToken = token?.trim() ?? '';
    if (trimmedToken.isEmpty) {
      return;
    }

    final userId = await _identityStore.getOrCreateUserId();
    final profileId = await _identityStore.getActiveProfileId();

    final currentProfile = profileId?.trim() ?? '';

    final uri = Uri.parse('https://${AppConfig.backendUrl}/devices/push-token').replace(
      queryParameters: {
        'user_id': userId,
        if (currentProfile.isNotEmpty) 'profile_id': currentProfile,
      },
    );

    final payload = jsonEncode({
      'token': trimmedToken,
      'platform': Platform.operatingSystem,
      'app_version': '',
    });

    final client = HttpClient();
    client.connectionTimeout = const Duration(seconds: 10);
    try {
      final request = await client.postUrl(uri);
      request.headers.contentType = ContentType.json;
      request.write(payload);
      final response = await request.close();
      await response.drain();
    } finally {
      client.close(force: true);
    }
  }
}
