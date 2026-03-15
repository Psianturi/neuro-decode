import 'package:camera/camera.dart';
import 'package:flutter/material.dart';

import '../../config/app_identity_store.dart';
import '../../theme/app_theme.dart';
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
    final surfaceColor = Theme.of(context).colorScheme.surface;
    final infoColor = Theme.of(context).colorScheme.primary.withValues(alpha: 0.10);

    return Scaffold(
      appBar: AppBar(title: const Text('Live Support')),
      body: ListView(
        padding: const EdgeInsets.all(NeuroColors.spacingLg),
        children: [
          Container(
            padding: const EdgeInsets.all(NeuroColors.spacingMd),
            decoration: BoxDecoration(
              color: surfaceColor,
              borderRadius: BorderRadius.circular(NeuroColors.radiusMd),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Ready for Real-Time Intervention',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: NeuroColors.spacingSm),
                Text(
                  'Use this mode when situations become intense. AI analyzes audio and visual cues in real time.',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ],
            ),
          ),
          const SizedBox(height: NeuroColors.spacingMd),
          _SessionModeCard(
            mode: _sessionMode,
            onChanged: (mode) => setState(() => _sessionMode = mode),
          ),
          const SizedBox(height: NeuroColors.spacingMd),
          ElevatedButton.icon(
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
          const SizedBox(height: NeuroColors.spacingSm),
          Text(
            'You can start immediately, or set a profile below to give Buddy more context for later sessions.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: NeuroColors.spacingMd),
          Container(
            padding: const EdgeInsets.all(NeuroColors.spacingMd),
            decoration: BoxDecoration(
              color: surfaceColor,
              borderRadius: BorderRadius.circular(NeuroColors.radiusMd),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Who is this support session for?',
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(fontSize: 18),
                ),
                const SizedBox(height: NeuroColors.spacingSm),
                Text(
                  'Use one profile ID per child or household context so Buddy can remember what helps.',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
                const SizedBox(height: NeuroColors.spacingMd),
                TextField(
                  controller: _profileIdController,
                  decoration: InputDecoration(
                    labelText: 'Profile ID',
                    hintText: 'Example: joy1 or home-evening-profile',
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(NeuroColors.radiusSm),
                    ),
                  ),
                  textInputAction: TextInputAction.done,
                  autocorrect: false,
                ),
                const SizedBox(height: NeuroColors.spacingSm),
                SizedBox(
                  width: double.infinity,
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
                const SizedBox(height: NeuroColors.spacingMd),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(NeuroColors.spacingSm + 4),
                  decoration: BoxDecoration(
                    color: infoColor,
                    borderRadius: BorderRadius.circular(NeuroColors.radiusSm),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(Icons.info_outline,
                          size: 18, color: NeuroColors.primary),
                      const SizedBox(width: NeuroColors.spacingSm),
                      Expanded(
                        child: Text(
                          'A profile helps Buddy recall triggers, calming strategies, and past sessions.',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: NeuroColors.spacingLg),
          OutlinedButton.icon(
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
        ],
      ),
    );
  }
}

enum SupportSessionMode {
  audioOnly,
  videoAndAudio,
}

class _SessionModeCard extends StatelessWidget {
  const _SessionModeCard({
    required this.mode,
    required this.onChanged,
  });

  final SupportSessionMode mode;
  final ValueChanged<SupportSessionMode> onChanged;

  @override
  Widget build(BuildContext context) {
    final surfaceColor = Theme.of(context).colorScheme.surface;

    return Container(
      padding: const EdgeInsets.all(NeuroColors.spacingMd),
      decoration: BoxDecoration(
        color: surfaceColor,
        borderRadius: BorderRadius.circular(NeuroColors.radiusMd),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Session Mode',
            style: Theme.of(context).textTheme.titleSmall,
          ),
          const SizedBox(height: NeuroColors.spacingSm),
          Text(
            'Audio only for consultation. Video + audio when the child is in distress and camera context is needed.',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const SizedBox(height: NeuroColors.spacingMd),
          Row(
            children: [
              Expanded(
                child: _ModeOption(
                  icon: Icons.mic,
                  label: 'Audio only',
                  selected: mode == SupportSessionMode.audioOnly,
                  onTap: () => onChanged(SupportSessionMode.audioOnly),
                ),
              ),
              const SizedBox(width: NeuroColors.spacingSm),
              Expanded(
                child: _ModeOption(
                  icon: Icons.videocam,
                  label: 'Video + audio',
                  selected: mode == SupportSessionMode.videoAndAudio,
                  onTap: () => onChanged(SupportSessionMode.videoAndAudio),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ModeOption extends StatelessWidget {
  const _ModeOption({
    required this.icon,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final selectedColor = Theme.of(context).colorScheme.primary;
    final inactiveColor =
        Theme.of(context).colorScheme.primary.withValues(alpha: 0.10);
    final mutedColor =
        Theme.of(context).textTheme.bodyMedium?.color ?? NeuroColors.textSecondary;

    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeInOut,
        padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 12),
        decoration: BoxDecoration(
          color: selected
              ? selectedColor.withValues(alpha: 0.12)
              : inactiveColor,
          borderRadius: BorderRadius.circular(NeuroColors.radiusMd),
          border: Border.all(
            color: selected ? selectedColor : Colors.transparent,
            width: 2,
          ),
        ),
        child: Column(
          children: [
            AnimatedScale(
              scale: selected ? 1.15 : 1.0,
              duration: const Duration(milliseconds: 250),
              child: Icon(
                icon,
                size: 32,
                color: selected ? selectedColor : mutedColor,
              ),
            ),
            const SizedBox(height: NeuroColors.spacingSm),
            Text(
              label,
              textAlign: TextAlign.center,
              style: TextStyle(
                fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                color: selected ? selectedColor : mutedColor,
              ),
            ),
            const SizedBox(height: NeuroColors.spacingXs),
            AnimatedOpacity(
              opacity: selected ? 1.0 : 0.0,
              duration: const Duration(milliseconds: 200),
              child: Icon(
                Icons.check_circle,
                size: 20,
                color: selectedColor,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
