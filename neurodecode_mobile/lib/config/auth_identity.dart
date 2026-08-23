import 'dart:convert';
import 'dart:io';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';

import 'app_config.dart';
import 'app_identity_store.dart';

enum MigrationState { none, pending, complete, conflict, expired }

/// Wraps Firebase Anonymous Auth as the caregiver's verified identity, and
/// drives the one-time migration of a device's pre-existing (unauthenticated)
/// local data onto that identity. See neurodecode_backend/app/routers/account.py
/// for the server side of the claim.
class AuthIdentity {
  AuthIdentity();

  /// Screens can listen to this to show a "syncing" state instead of a
  /// confident empty state while a legacy claim is in flight — a transient
  /// failure must never read to the caregiver as "your history is gone".
  static final ValueNotifier<MigrationState> migrationState =
      ValueNotifier<MigrationState>(MigrationState.none);

  static bool _claimAttemptedThisSession = false;

  String get uid {
    final user = FirebaseAuth.instance.currentUser;
    if (user == null) {
      throw StateError('AuthIdentity.uid read before sign-in completed');
    }
    return user.uid;
  }

  Future<String> getIdToken({bool forceRefresh = false}) async {
    final user = FirebaseAuth.instance.currentUser;
    if (user == null) {
      throw StateError('AuthIdentity.getIdToken called before sign-in completed');
    }
    final token = await user.getIdToken(forceRefresh);
    if (token == null || token.isEmpty) {
      throw StateError('Failed to obtain a Firebase ID token');
    }
    return token;
  }

  /// Ensures a signed-in Firebase user exists (anonymous sign-in is
  /// invisible to the caregiver — no login screen, no credentials). Call
  /// once at app startup before any backend call is made.
  Future<void> ensureSignedIn() async {
    if (FirebaseAuth.instance.currentUser != null) {
      return;
    }
    await FirebaseAuth.instance.signInAnonymously();
  }

  /// One-time, resumable-on-retry migration of this device's pre-Firebase
  /// local data to the caller's verified uid. Safe to call every app launch:
  /// it no-ops immediately once a terminal outcome has been persisted, and
  /// only actually calls the backend when there is a legacy id and no
  /// terminal outcome recorded yet. Never marks itself done on a transient
  /// failure, so it keeps retrying on later launches until the backend
  /// responds definitively.
  Future<void> attemptLegacyClaimIfNeeded({AppIdentityStore? identityStore}) async {
    if (_claimAttemptedThisSession) {
      return;
    }
    _claimAttemptedThisSession = true;

    final store = identityStore ?? AppIdentityStore();

    final existingStatus = await store.getLegacyClaimStatus();
    if (existingStatus != null) {
      migrationState.value = MigrationState.complete;
      return;
    }

    final legacyUserId = await store.readExistingUserId();
    if (legacyUserId == null || legacyUserId == uid) {
      // Fresh install (no legacy id) or already-migrated device — nothing to do.
      migrationState.value = MigrationState.complete;
      return;
    }

    migrationState.value = MigrationState.pending;

    final client = HttpClient();
    client.connectionTimeout = const Duration(seconds: 10);
    try {
      final token = await getIdToken();
      final uri = Uri.parse('https://${AppConfig.backendUrl}/account/claim-legacy');
      final request = await client.postUrl(uri);
      request.headers.contentType = ContentType.json;
      request.headers.set('authorization', 'Bearer $token');
      request.write(jsonEncode({'legacy_user_id': legacyUserId}));
      final response = await request.close();
      await response.drain<void>();

      switch (response.statusCode) {
        case 200:
          await store.setLegacyClaimStatus('complete');
          migrationState.value = MigrationState.complete;
          break;
        case 409:
          await store.setLegacyClaimStatus('conflict');
          migrationState.value = MigrationState.conflict;
          break;
        case 410:
          await store.setLegacyClaimStatus('expired');
          migrationState.value = MigrationState.expired;
          break;
        default:
          // Transient failure (5xx, 401 from a not-yet-fresh token, etc.) —
          // no flag persisted, so this is retried on the next app launch.
          migrationState.value = MigrationState.none;
      }
    } catch (_) {
      // Network error/timeout — same as above, retry next launch.
      migrationState.value = MigrationState.none;
    } finally {
      client.close(force: true);
    }
  }
}
