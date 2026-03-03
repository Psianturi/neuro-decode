import 'package:flutter/material.dart';
import 'package:camera/camera.dart';

import 'app/neurodecode_app.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  List<CameraDescription> cameras = [];
  try {
    cameras = await availableCameras();
  } catch (_) {
    cameras = [];
  }

  runApp(NeuroDecodeApp(cameras: cameras));
}
