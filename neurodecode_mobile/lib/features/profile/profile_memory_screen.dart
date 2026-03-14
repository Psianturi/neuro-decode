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
  static const List<_QuickMemoryTemplate> _quickTemplates = [
    _QuickMemoryTemplate(
      category: 'trigger',
      title: 'Common trigger',
      note: 'Loud environments or sudden noises can trigger distress.',
    ),
    _QuickMemoryTemplate(
      category: 'calming',
      title: 'Calming preference',
      note: 'Short, gentle phrases and slow breathing prompts help most.',
    ),
    _QuickMemoryTemplate(
      category: 'routine',
      title: 'Helpful routine',
      note:
          'Offer water, reduce stimulation, and give 30-60 seconds of space first.',
    ),
    _QuickMemoryTemplate(
      category: 'safety',
      title: 'Safety note',
      note: 'Avoid rapid instructions; one calm step at a time works better.',
    ),
  ];

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
  ProfileMemoryContext? _memoryContext;

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
        widget.service.fetchMemoryContext(widget.profileId),
      ]);
      if (!mounted) {
        return;
      }
      final profile = results[0] as ProfileRecord?;
      final items = results[1] as List<ProfileMemoryItem>;
      final context = results[2] as ProfileMemoryContext;
      _nameController.text = profile?.name ?? '';
      _childNameController.text = profile?.childName ?? '';
      _caregiverNameController.text = profile?.caregiverName ?? '';
      _notesController.text = profile?.notes ?? '';
      setState(() {
        _memoryItems = items;
        _memoryContext = context;
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
      await _load();
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

  void _applyTemplate(_QuickMemoryTemplate template) {
    _memoryCategoryController.text = template.category;
    _memoryNoteController.text = template.note;
  }

  int get _profileCompletionScore {
    var score = 0;
    if (_nameController.text.trim().isNotEmpty) score++;
    if (_childNameController.text.trim().isNotEmpty) score++;
    if (_caregiverNameController.text.trim().isNotEmpty) score++;
    if (_notesController.text.trim().isNotEmpty) score++;
    return score;
  }

  @override
  Widget build(BuildContext context) {
    final completion = _profileCompletionScore;
    final profileHeadline = _nameController.text.trim().isNotEmpty
        ? _nameController.text.trim()
        : widget.profileId;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Profile Workspace'),
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
                  profileHeadline,
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: 8),
                Text(
                  'Profile ID: ${widget.profileId}',
                  style: const TextStyle(
                    color: NeuroColors.textSecondary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 10),
                const Text(
                  'This page teaches Buddy how to respond more personally. Add only the details that actually help in stressful moments: names, calming preferences, triggers, routines, and safety notes.',
                  style: TextStyle(color: NeuroColors.textSecondary),
                ),
                const SizedBox(height: 14),
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: [
                    _StatPill(
                      label: 'Profile completeness',
                      value: '$completion/4',
                    ),
                    _StatPill(
                      label: 'Memory notes',
                      value:
                          '${_memoryContext?.memoryItemCount ?? _memoryItems.length}',
                    ),
                    _StatPill(
                      label: 'Recent sessions',
                      value: '${_memoryContext?.recentSessionCount ?? 0}',
                    ),
                  ],
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
                  'What should go here?',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 10),
                const _GuideBullet(
                  title: 'Profile details',
                  text:
                      'Who is being supported, who usually assists, and one or two important support notes.',
                ),
                const SizedBox(height: 8),
                const _GuideBullet(
                  title: 'Memory notes',
                  text:
                      'Short facts Buddy should remember later, for example triggers, calming phrases, safe routines, or warnings.',
                ),
                const SizedBox(height: 8),
                const _GuideBullet(
                  title: 'Best style',
                  text:
                      'Write plain real-world notes. Think: “what would help a caregiver in the next intense moment?”',
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
                  '1. Basic profile summary',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 6),
                const Text(
                  'Keep this short. These fields make later summaries and memory retrieval easier to understand.',
                  style: TextStyle(color: NeuroColors.textSecondary),
                ),
                const SizedBox(height: 12),
                _LabeledField(
                  label: 'Display name for this profile',
                  hintText: 'Example: Joy - evening support profile',
                  controller: _nameController,
                ),
                const SizedBox(height: 12),
                _LabeledField(
                  label: 'Child name',
                  hintText: 'Example: Joy',
                  controller: _childNameController,
                ),
                const SizedBox(height: 12),
                _LabeledField(
                  label: 'Primary caregiver name',
                  hintText: 'Example: Mother, father, therapist, aunt',
                  controller: _caregiverNameController,
                ),
                const SizedBox(height: 12),
                _LabeledField(
                  label: 'One-paragraph support summary',
                  hintText:
                      'Example: Joy responds best to soft voice, simple steps, and a short pause before new instructions.',
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
                  '2. Add a memory note',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 6),
                const Text(
                  'Use this for recurring details Buddy should remember across sessions.',
                  style: TextStyle(color: NeuroColors.textSecondary),
                ),
                const SizedBox(height: 14),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: _quickTemplates
                      .map(
                        (template) => ActionChip(
                          label: Text(template.title),
                          onPressed: () =>
                              setState(() => _applyTemplate(template)),
                        ),
                      )
                      .toList(),
                ),
                const SizedBox(height: 12),
                _LabeledField(
                  label: 'Category',
                  hintText: 'trigger, calming, routine, safety, preference',
                  controller: _memoryCategoryController,
                ),
                const SizedBox(height: 12),
                _LabeledField(
                  label: 'Memory note',
                  hintText:
                      'Example: Offer slow breathing prompt before asking any follow-up questions.',
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
                  '3. Stored memory',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 10),
                if ((_memoryContext?.context ?? '').isNotEmpty) ...[
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: NeuroColors.surfaceVariant,
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Current memory summary',
                          style: TextStyle(fontWeight: FontWeight.w700),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          _memoryContext!.context,
                          style:
                              const TextStyle(color: NeuroColors.textSecondary),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                ],
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
    this.hintText,
    this.minLines = 1,
    this.maxLines = 1,
  });

  final String label;
  final TextEditingController controller;
  final String? hintText;
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
        hintText: hintText,
        border: const OutlineInputBorder(),
      ),
    );
  }
}

class _GuideBullet extends StatelessWidget {
  const _GuideBullet({required this.title, required this.text});

  final String title;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 8,
          height: 8,
          margin: const EdgeInsets.only(top: 6),
          decoration: const BoxDecoration(
            color: NeuroColors.primary,
            shape: BoxShape.circle,
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: RichText(
            text: TextSpan(
              style: DefaultTextStyle.of(context).style,
              children: [
                TextSpan(
                  text: '$title: ',
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
                TextSpan(text: text),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _StatPill extends StatelessWidget {
  const _StatPill({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: NeuroColors.surfaceVariant,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            value,
            style: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              color: NeuroColors.textPrimary,
            ),
          ),
          const SizedBox(height: 2),
          Text(label, style: const TextStyle(color: NeuroColors.textSecondary)),
        ],
      ),
    );
  }
}

class _QuickMemoryTemplate {
  const _QuickMemoryTemplate({
    required this.category,
    required this.title,
    required this.note,
  });

  final String category;
  final String title;
  final String note;
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
