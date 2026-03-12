import 'package:camera/camera.dart';
import 'package:flutter/material.dart';

import '../../config/app_identity_store.dart';
import '../../theme/app_theme.dart';
import '../home/history_insights_screen.dart';
import '../home/session_summary_service.dart';
import '../live_agent/live_agent_screen.dart';

class SupportHubScreen extends StatefulWidget {
  const SupportHubScreen({
    super.key,
    required this.cameras,
  });

  final List<CameraDescription> cameras;

  @override
  State<SupportHubScreen> createState() => _SupportHubScreenState();
}

class _SupportHubScreenState extends State<SupportHubScreen> {
  bool _observerEnabled = false;
  final SessionSummaryService _summaryService = SessionSummaryService();
  final AppIdentityStore _identityStore = AppIdentityStore();
  final TextEditingController _profileIdController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadStoredProfileId();
  }

  Future<void> _loadStoredProfileId() async {
    final profileId = await _identityStore.getActiveProfileId();
    if (!mounted || profileId == null) {
      return;
    }
    _profileIdController.text = profileId;
  }

  @override
  void dispose() {
    _profileIdController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Live Support')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: NeuroColors.surface,
              borderRadius: BorderRadius.circular(18),
            ),
            child: const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Ready for Real-Time Intervention',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700),
                ),
                SizedBox(height: 8),
                Text(
                  'Use this mode when situations become intense. AI analyzes audio and visual cues in real time.',
                  style: TextStyle(color: NeuroColors.textSecondary),
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          Container(
            decoration: BoxDecoration(
              color: NeuroColors.surface,
              borderRadius: BorderRadius.circular(18),
            ),
            child: SwitchListTile.adaptive(
              value: _observerEnabled,
              title: const Text('Camera Observer'),
              subtitle:
                  const Text('Send periodic frame for visual cue detection'),
              onChanged: (value) {
                setState(() {
                  _observerEnabled = value;
                });
              },
            ),
          ),
          const SizedBox(height: 14),
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: NeuroColors.surface,
              borderRadius: BorderRadius.circular(18),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Profile ID',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 8),
                const Text(
                  'Optional for local testing. Fill this with a real child or caregiver profile ID when you want personalized memory retrieval.',
                  style: TextStyle(color: NeuroColors.textSecondary),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _profileIdController,
                  decoration: const InputDecoration(
                    hintText: 'example: demo-child-001',
                    border: OutlineInputBorder(),
                  ),
                  textInputAction: TextInputAction.done,
                  autocorrect: false,
                ),
              ],
            ),
          ),
          const SizedBox(height: 18),
          SizedBox(
            height: 56,
            child: ElevatedButton.icon(
              onPressed: () async {
                final profileId = _profileIdController.text.trim();
                final userId = await _identityStore.getOrCreateUserId();
                await _identityStore.setActiveProfileId(
                  profileId.isEmpty ? null : profileId,
                );
                await Navigator.push(
                  // ignore: use_build_context_synchronously
                  context,
                  MaterialPageRoute(
                    builder: (_) => LiveAgentScreen(
                      cameras: widget.cameras,
                      observerEnabled: _observerEnabled,
                      userId: userId,
                      profileId: profileId.isEmpty ? null : profileId,
                    ),
                  ),
                );
              },
              icon: const Icon(Icons.play_circle_fill),
              label: const Text('START LIVE SUPPORT'),
              style: ElevatedButton.styleFrom(
                elevation: 6,
                shadowColor: NeuroColors.primary.withValues(alpha: 0.28),
              ),
            ),
          ),
          const SizedBox(height: 12),
          SizedBox(
            height: 50,
            child: OutlinedButton.icon(
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) =>
                        HistoryInsightsScreen(service: _summaryService),
                  ),
                );
              },
              icon: const Icon(Icons.history),
              label: const Text('VIEW HISTORY / INSIGHTS'),
            ),
          ),
        ],
      ),
    );
  }
}
