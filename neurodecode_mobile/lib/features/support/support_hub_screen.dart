import 'package:camera/camera.dart';
import 'package:flutter/material.dart';

import '../../config/app_identity_store.dart';
import '../../theme/app_theme.dart';
import '../home/history_insights_screen.dart';
import '../home/session_summary_service.dart';
import '../live_agent/live_agent_screen.dart';
import '../profile/profile_picker_screen.dart';
import '../profile/profile_memory_screen.dart';

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
  SupportSessionMode _sessionMode = SupportSessionMode.audioOnly;
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
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Session Mode',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Use Audio only for caregiver consultation. Use Video + audio when the child is currently in distress and camera context is needed.',
                    style: TextStyle(color: NeuroColors.textSecondary),
                  ),
                  const SizedBox(height: 12),
                  SegmentedButton<SupportSessionMode>(
                    segments: const [
                      ButtonSegment<SupportSessionMode>(
                        value: SupportSessionMode.audioOnly,
                        icon: Icon(Icons.mic),
                        label: Text('Audio only'),
                      ),
                      ButtonSegment<SupportSessionMode>(
                        value: SupportSessionMode.videoAndAudio,
                        icon: Icon(Icons.videocam),
                        label: Text('Video + audio'),
                      ),
                    ],
                    selected: <SupportSessionMode>{_sessionMode},
                    onSelectionChanged: (selection) {
                      setState(() {
                        _sessionMode = selection.first;
                      });
                    },
                  ),
                ],
              ),
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
                  'Who is this support session for?',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 8),
                const Text(
                  'Use one profile ID for one child or household context. Buddy will use it to remember helpful notes, recurring triggers, and past support patterns.',
                  style: TextStyle(color: NeuroColors.textSecondary),
                ),
                const SizedBox(height: 14),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: NeuroColors.surfaceVariant,
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: const Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Why this matters',
                        style: TextStyle(fontWeight: FontWeight.w700),
                      ),
                      SizedBox(height: 6),
                      Text(
                        'A profile makes later sessions feel more informed. Example notes: what usually triggers distress, what calming words help, and what a caregiver should avoid saying.',
                        style: TextStyle(color: NeuroColors.textSecondary),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _profileIdController,
                  decoration: const InputDecoration(
                    labelText: 'Profile ID',
                    hintText: 'Example: joy1 or home-evening-profile',
                    border: OutlineInputBorder(),
                  ),
                  textInputAction: TextInputAction.done,
                  autocorrect: false,
                ),
                const SizedBox(height: 10),
                Align(
                  alignment: Alignment.centerLeft,
                  child: OutlinedButton.icon(
                    onPressed: () async {
                      final selected = await Navigator.push<String>(
                        context,
                        MaterialPageRoute(
                          builder: (_) => ProfilePickerScreen(
                              identityStore: _identityStore),
                        ),
                      );
                      if (!mounted || selected == null || selected.isEmpty) {
                        return;
                      }
                      setState(() {
                        _profileIdController.text = selected;
                      });
                    },
                    icon: const Icon(Icons.history),
                    label: const Text('SELECT SAVED PROFILE ID'),
                  ),
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
                      observerEnabled:
                          _sessionMode == SupportSessionMode.videoAndAudio,
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
                final profileId = _profileIdController.text.trim();
                if (profileId.isEmpty) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text(
                          'Enter a Profile ID before opening profile memory.'),
                    ),
                  );
                  return;
                }
                _identityStore.setActiveProfileId(profileId);
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => ProfileMemoryScreen(profileId: profileId),
                  ),
                );
              },
              icon: const Icon(Icons.psychology_alt_outlined),
              label: const Text('SET UP PROFILE WORKSPACE'),
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

enum SupportSessionMode {
  audioOnly,
  videoAndAudio,
}
