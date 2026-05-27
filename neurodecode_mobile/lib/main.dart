import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:pendo_sdk/pendo_sdk.dart';

import 'app/neurodecode_app.dart';
import 'config/app_identity_store.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  await PendoSDK.setup('40da3a81-8dea-47d6-8099-f25e18ba3fdf');

  final identityStore = AppIdentityStore();
  final userId = await identityStore.getOrCreateUserId();
  final activeProfileId = await identityStore.getActiveProfileId();

  await PendoSDK.startSession(
    userId,
    "",
    {
      "userId": userId,
      "activeProfileId": activeProfileId ?? "",
    },
    {},
  );

  List<CameraDescription> cameras = [];
  try {
    cameras = await availableCameras();
  } catch (_) {
    cameras = [];
  }

  runApp(
    PendoActionListener(
      child: NeuroDecodeApp(cameras: cameras),
    ),
  );
}
