import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:neurodecode_mobile/app/neurodecode_app.dart';

void main() {
  testWidgets('App boots and renders MaterialApp', (WidgetTester tester) async {
    await tester.pumpWidget(const NeuroDecodeApp(cameras: []));
    // Allow theme load async to settle without triggering network calls
    await tester.pump(const Duration(milliseconds: 100));

    // MaterialApp renders — verify the widget tree is non-empty
    expect(find.byType(MaterialApp), findsOneWidget);
  });
}
