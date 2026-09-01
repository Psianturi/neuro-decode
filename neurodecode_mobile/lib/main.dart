import 'dart:async';

import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:firebase_core/firebase_core.dart';

import 'app/neurodecode_app.dart';
import 'config/auth_identity.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Anonymous Firebase sign-in is invisible to the caregiver (no login
  // screen) — it just gives the backend a verifiable identity in place of
  // the old unauthenticated local id. Must happen before any backend call.
  final authIdentity = AuthIdentity();
  try {
    await Firebase.initializeApp();
    await authIdentity.ensureSignedIn();
    // Fire-and-forget: migrates this device's pre-existing data (if any) to
    // the new uid. Never blocks startup — screens watch
    // AuthIdentity.migrationState to show a syncing indicator meanwhile.
    unawaited(authIdentity.attemptLegacyClaimIfNeeded());
  } catch (_) {
    // Firebase not configured for this build/runtime — the app still runs,
    // but authenticated backend calls will fail until this is resolved.
  }

  List<CameraDescription> cameras = [];
  try {
    cameras = await availableCameras();
  } catch (_) {
    cameras = [];
  }

  runApp(NeuroDecodeApp(cameras: cameras));
}
