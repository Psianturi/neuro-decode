import 'dart:convert';
import 'dart:io';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';

import '../../config/app_config.dart';
import '../../config/app_identity_store.dart';
import '../../config/auth_identity.dart';

class PushRegistrationService {
  PushRegistrationService({AppIdentityStore? identityStore, AuthIdentity? authIdentity})
      : _identityStore = identityStore ?? AppIdentityStore(),
        _authIdentity = authIdentity ?? AuthIdentity();

  final AppIdentityStore _identityStore;
  final AuthIdentity _authIdentity;

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

    final idToken = await _authIdentity.getIdToken();
    final profileId = await _identityStore.getActiveProfileId();

    final currentProfile = profileId?.trim() ?? '';

    final uri = Uri.parse('https://${AppConfig.backendUrl}/devices/push-token').replace(
      queryParameters: {
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
      request.headers.set('authorization', 'Bearer $idToken');
      request.write(payload);
      final response = await request.close();
      await response.drain();
    } finally {
      client.close(force: true);
    }
  }
}
