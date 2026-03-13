import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../theme/app_theme.dart';
import 'profile_memory_service.dart';

class ProfileMemoryScreen extends StatefulWidget {
  ProfileMemoryScreen({
    super.key,
    required this.profileId,
    ProfileMemoryService? service,
  }) : service = service ?? ProfileMemoryService();

  final String profileId;
  final ProfileMemoryService service;

  @override
  State<ProfileMemoryScreen> createState() => _ProfileMemoryScreenState();
}

class _ProfileMemoryScreenState extends State<ProfileMemoryScreen> {
  final TextEditingController _nameController = TextEditingController();
  final TextEditingController _childNameController = TextEditingController();
  final TextEditingController _caregiverNameController =
      TextEditingController();
  final TextEditingController _notesController = TextEditingController();
  final TextEditingController _memoryNoteController = TextEditingController();
  final TextEditingController _memoryCategoryController =
      TextEditingController(text: 'general');

  bool _isLoading = false;
  bool _isSavingProfile = false;
  bool _isAddingMemory = false;
  String? _error;
  String _selectedConfidence = 'medium';
  List<ProfileMemoryItem> _memoryItems = const <ProfileMemoryItem>[];

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _nameController.dispose();
    _childNameController.dispose();
    _caregiverNameController.dispose();
    _notesController.dispose();
    _memoryNoteController.dispose();
    _memoryCategoryController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    if (_isLoading) {
      return;
    }
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final results = await Future.wait<Object?>([
        widget.service.fetchProfile(widget.profileId),
        widget.service.fetchMemory(widget.profileId),
      ]);
      if (!mounted) {
        return;
      }
      final profile = results[0] as ProfileRecord?;
      final items = results[1] as List<ProfileMemoryItem>;
      _nameController.text = profile?.name ?? '';
      _childNameController.text = profile?.childName ?? '';
      _caregiverNameController.text = profile?.caregiverName ?? '';
      _notesController.text = profile?.notes ?? '';
      setState(() {
        _memoryItems = items;
      });
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = e.toString();
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _saveProfile() async {
    if (_isSavingProfile) {
      return;
    }
    setState(() {
      _isSavingProfile = true;
    });
    try {
      await widget.service.saveProfile(
        profileId: widget.profileId,
        name: _nameController.text,
        childName: _childNameController.text,
        caregiverName: _caregiverNameController.text,
        notes: _notesController.text,
      );
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Profile saved.')),
      );
    } catch (e) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to save profile: $e')),
      );
    } finally {
      if (mounted) {
        setState(() {
          _isSavingProfile = false;
        });
      }
    }
  }

  Future<void> _addMemory() async {
    final note = _memoryNoteController.text.trim();
    final category = _memoryCategoryController.text.trim();
    if (note.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Memory note cannot be empty.')),
      );
      return;
    }
    if (_isAddingMemory) {
      return;
    }
    setState(() {
      _isAddingMemory = true;
    });
    try {
      await widget.service.addMemory(
        profileId: widget.profileId,
        category: category.isEmpty ? 'general' : category,
        note: note,
        confidence: _selectedConfidence,
      );
      _memoryNoteController.clear();
      _memoryCategoryController.text = 'general';
      await _load();
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Memory note added.')),
      );
    } catch (e) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to add memory: $e')),
      );
    } finally {
      if (mounted) {
        setState(() {
          _isAddingMemory = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Profile Memory'),
        actions: [
          IconButton(
            onPressed: _isLoading ? null : _load,
            icon: _isLoading
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.refresh),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          _SectionCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Active profile: ${widget.profileId}',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                const Text(
                  'Store profile details and memory notes that the live agent can use for personalized retrieval.',
                  style: TextStyle(color: NeuroColors.textSecondary),
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          _SectionCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Profile details',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 12),
                _LabeledField(
                    label: 'Display name', controller: _nameController),
                const SizedBox(height: 12),
                _LabeledField(
                    label: 'Child name', controller: _childNameController),
                const SizedBox(height: 12),
                _LabeledField(
                  label: 'Caregiver name',
                  controller: _caregiverNameController,
                ),
                const SizedBox(height: 12),
                _LabeledField(
                  label: 'Support notes',
                  controller: _notesController,
                  minLines: 3,
                  maxLines: 5,
                ),
                const SizedBox(height: 14),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: _isSavingProfile ? null : _saveProfile,
                    icon: _isSavingProfile
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.save),
                    label: const Text('SAVE PROFILE'),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          _SectionCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Add memory note',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 12),
                _LabeledField(
                  label: 'Category',
                  controller: _memoryCategoryController,
                ),
                const SizedBox(height: 12),
                _LabeledField(
                  label: 'Memory note',
                  controller: _memoryNoteController,
                  minLines: 3,
                  maxLines: 5,
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  value: _selectedConfidence,
                  decoration: const InputDecoration(
                    labelText: 'Confidence',
                    border: OutlineInputBorder(),
                  ),
                  items: const [
                    DropdownMenuItem(value: 'low', child: Text('Low')),
                    DropdownMenuItem(value: 'medium', child: Text('Medium')),
                    DropdownMenuItem(value: 'high', child: Text('High')),
                  ],
                  onChanged: (value) {
                    if (value == null) {
                      return;
                    }
                    setState(() {
                      _selectedConfidence = value;
                    });
                  },
                ),
                const SizedBox(height: 14),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: _isAddingMemory ? null : _addMemory,
                    icon: _isAddingMemory
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.note_add),
                    label: const Text('ADD MEMORY NOTE'),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          _SectionCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Stored memory',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 10),
                if (_error != null && _memoryItems.isEmpty)
                  Text(
                    _error!,
                    style: const TextStyle(color: Color(0xFFD35353)),
                  )
                else if (_memoryItems.isEmpty)
                  const Text(
                    'No memory notes yet. Add recurring triggers, calming preferences, or context that should inform live support.',
                    style: TextStyle(color: NeuroColors.textSecondary),
                  )
                else
                  for (final item in _memoryItems) _MemoryTile(item: item),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionCard extends StatelessWidget {
  const _SectionCard({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: NeuroColors.surface,
        borderRadius: BorderRadius.circular(18),
      ),
      child: child,
    );
  }
}

class _LabeledField extends StatelessWidget {
  const _LabeledField({
    required this.label,
    required this.controller,
    this.minLines = 1,
    this.maxLines = 1,
  });

  final String label;
  final TextEditingController controller;
  final int minLines;
  final int maxLines;

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      minLines: minLines,
      maxLines: maxLines,
      decoration: InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
      ),
    );
  }
}

class _MemoryTile extends StatelessWidget {
  const _MemoryTile({required this.item});

  final ProfileMemoryItem item;

  @override
  Widget build(BuildContext context) {
    final subtitleBits = <String>[
      item.category,
      item.confidence,
      if (item.updatedAtUtc.isNotEmpty) _formatTimestamp(item.updatedAtUtc),
      if (!item.active) 'inactive',
    ];

    return Container(
      margin: const EdgeInsets.only(top: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: NeuroColors.surfaceVariant,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            item.note,
            style: const TextStyle(
              color: NeuroColors.textPrimary,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            subtitleBits.join(' • '),
            style: const TextStyle(color: NeuroColors.textSecondary),
          ),
        ],
      ),
    );
  }

  static String _formatTimestamp(String raw) {
    try {
      return DateFormat('dd MMM yyyy').format(DateTime.parse(raw).toLocal());
    } catch (_) {
      return raw;
    }
  }
}
