import 'package:flutter/material.dart';

import '../../config/app_identity_store.dart';
import '../../theme/app_theme.dart';

class ProfilePickerScreen extends StatefulWidget {
  const ProfilePickerScreen({
    super.key,
    required this.identityStore,
  });

  final AppIdentityStore identityStore;

  @override
  State<ProfilePickerScreen> createState() => _ProfilePickerScreenState();
}

class _ProfilePickerScreenState extends State<ProfilePickerScreen> {
  bool _isLoading = false;
  List<String> _items = const <String>[];
  String? _active;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (_isLoading) return;
    setState(() {
      _isLoading = true;
    });
    final results = await Future.wait<Object?>([
      widget.identityStore.listRecentProfileIds(),
      widget.identityStore.getActiveProfileId(),
    ]);
    if (!mounted) return;
    setState(() {
      _items = results[0] as List<String>;
      _active = results[1] as String?;
      _isLoading = false;
    });
  }

  Future<void> _removeProfileId(String profileId) async {
    await widget.identityStore.removeRecentProfileId(profileId);
    await _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Saved Profile IDs')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text(
            'Select a profile ID to fill Support quickly. The most recent IDs are shown first.',
            style: TextStyle(color: NeuroColors.textSecondary),
          ),
          const SizedBox(height: 12),
          if (_isLoading)
            const Padding(
              padding: EdgeInsets.only(top: 36),
              child: Center(child: CircularProgressIndicator()),
            )
          else if (_items.isEmpty)
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: NeuroColors.surface,
                borderRadius: BorderRadius.circular(14),
              ),
              child: const Text(
                'No saved profile ID yet. Start one session first and it will appear here.',
                style: TextStyle(color: NeuroColors.textSecondary),
              ),
            )
          else
            for (final profileId in _items)
              Card(
                margin: const EdgeInsets.only(bottom: 10),
                child: ListTile(
                  leading: Icon(
                    profileId == _active ? Icons.check_circle : Icons.badge,
                    color: profileId == _active
                        ? NeuroColors.secondary
                        : NeuroColors.primary,
                  ),
                  title: Text(profileId),
                  subtitle: Text(
                    profileId == _active ? 'Currently active' : 'Tap to use',
                  ),
                  trailing: IconButton(
                    onPressed: () => _removeProfileId(profileId),
                    icon: const Icon(Icons.delete_outline),
                    tooltip: 'Remove',
                  ),
                  onTap: () => Navigator.pop(context, profileId),
                ),
              ),
        ],
      ),
    );
  }
}
