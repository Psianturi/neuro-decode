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
  static const List<String> _triggerOptions = [
    'Loud noise',
    'Crowded place',
    'Sudden change',
    'Waiting too long',
    'Denied request',
    'Fatigue',
  ];
  static const List<String> _calmingOptions = [
    'Soft voice',
    'Short phrases',
    'Breathing prompt',
    'Quiet space',
    'Favorite object',
    'Water break',
  ];
  static const List<String> _communicationOptions = [
    'One step at a time',
    'Pause before repeating',
    'Avoid touching first',
    'Give reassurance first',
    'Use simple choices',
    'Keep tone gentle',
  ];
  static const List<String> _memoryCategories = [
    'trigger',
    'calming',
    'routine',
    'safety',
    'preference',
  ];
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
  String _selectedMemoryCategory = 'trigger';
  List<ProfileMemoryItem> _memoryItems = const <ProfileMemoryItem>[];
  ProfileMemoryContext? _memoryContext;
  Set<String> _selectedTriggers = <String>{};
  Set<String> _selectedCalmingSupports = <String>{};
  Set<String> _selectedCommunicationPrefs = <String>{};

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
        _selectedTriggers = {...?profile?.triggerTags};
        _selectedCalmingSupports = {...?profile?.calmingTags};
        _selectedCommunicationPrefs = {...?profile?.communicationTags};
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
        generatedSummary: _generatedSummary,
        triggerTags: _selectedTriggers.toList(),
        calmingTags: _selectedCalmingSupports.toList(),
        communicationTags: _selectedCommunicationPrefs.toList(),
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
        category: _selectedMemoryCategory,
        note: note,
        confidence: _selectedConfidence,
      );
      _memoryNoteController.clear();
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
    _selectedMemoryCategory = template.category;
    _memoryNoteController.text = template.note;
  }

  void _toggleSelection(Set<String> bucket, String value) {
    setState(() {
      if (bucket.contains(value)) {
        bucket.remove(value);
      } else {
        bucket.add(value);
      }
    });
  }

  int get _profileCompletionScore {
    var score = 0;
    if (_childNameController.text.trim().isNotEmpty) score++;
    if (_caregiverNameController.text.trim().isNotEmpty) score++;
    if (_selectedTriggers.isNotEmpty || _selectedCalmingSupports.isNotEmpty) {
      score++;
    }
    if (_selectedCommunicationPrefs.isNotEmpty ||
        _notesController.text.trim().isNotEmpty) {
      score++;
    }
    return score;
  }

  String get _generatedSummary {
    final child = _childNameController.text.trim();
    final caregiver = _caregiverNameController.text.trim();
    final extra = _notesController.text.trim();
    final parts = <String>[];

    if (child.isNotEmpty) {
      parts.add('$child is the child currently being supported.');
    }
    if (caregiver.isNotEmpty) {
      parts.add('Primary caregiver: $caregiver.');
    }
    if (_selectedTriggers.isNotEmpty) {
      parts.add('Common triggers: ${_selectedTriggers.join(', ')}.');
    }
    if (_selectedCalmingSupports.isNotEmpty) {
      parts.add(
          'Helpful calming supports: ${_selectedCalmingSupports.join(', ')}.');
    }
    if (_selectedCommunicationPrefs.isNotEmpty) {
      parts.add(
          'Best communication style: ${_selectedCommunicationPrefs.join(', ')}.');
    }
    if (extra.isNotEmpty) {
      parts.add(extra);
    }

    if (parts.isEmpty) {
      return 'Add child name, caregiver name, and a few support choices so Buddy can build a useful summary here.';
    }
    return parts.join(' ');
  }

  @override
  Widget build(BuildContext context) {
    final completion = _profileCompletionScore;
    final profileHeadline = _childNameController.text.trim().isNotEmpty
        ? _childNameController.text.trim()
        : (_nameController.text.trim().isNotEmpty
            ? _nameController.text.trim()
            : widget.profileId);

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
                  'This page teaches Buddy how to respond more personally. Fill only the essentials, then choose the support patterns that usually help.',
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
                      'Only the essentials: child name, caregiver name, and a simple profile label if you want one.',
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
                  '1. Essential details',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 6),
                const Text(
                  'You do not need a long form. Start with the child and caregiver names. Everything else can be added later.',
                  style: TextStyle(color: NeuroColors.textSecondary),
                ),
                const SizedBox(height: 12),
                _LabeledField(
                  label: 'Optional profile label',
                  hintText: 'Example: Joy - evening routine',
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
                  label: 'Anything else Buddy should know?',
                  hintText: 'Optional detail not covered by the choices below.',
                  controller: _notesController,
                  minLines: 3,
                  maxLines: 5,
                ),
                const SizedBox(height: 14),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(NeuroColors.spacingMd - 2),
                  decoration: BoxDecoration(
                    color: NeuroColors.surfaceVariant,
                    borderRadius: BorderRadius.circular(NeuroColors.radiusSm),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Live summary preview',
                        style: TextStyle(fontWeight: FontWeight.w700),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        _generatedSummary,
                        style:
                            const TextStyle(color: NeuroColors.textSecondary),
                      ),
                    ],
                  ),
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
                  '2. Support preferences',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 6),
                const Text(
                  'Choose the patterns that best describe what usually triggers distress and what usually helps.',
                  style: TextStyle(color: NeuroColors.textSecondary),
                ),
                const SizedBox(height: 14),
                _ChoiceSection(
                  title: 'Common triggers',
                  options: _triggerOptions,
                  selected: _selectedTriggers,
                  onTap: (value) => _toggleSelection(_selectedTriggers, value),
                ),
                const SizedBox(height: 12),
                _ChoiceSection(
                  title: 'Helpful calming supports',
                  options: _calmingOptions,
                  selected: _selectedCalmingSupports,
                  onTap: (value) =>
                      _toggleSelection(_selectedCalmingSupports, value),
                ),
                const SizedBox(height: 12),
                _ChoiceSection(
                  title: 'Best communication style',
                  options: _communicationOptions,
                  selected: _selectedCommunicationPrefs,
                  onTap: (value) =>
                      _toggleSelection(_selectedCommunicationPrefs, value),
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
                    label: const Text('SAVE SUPPORT PREFERENCES'),
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
                  '3. Optional memory note',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 12),
                const Text(
                  'Only use this if there is something important that does not fit the choices above.',
                  style: TextStyle(color: NeuroColors.textSecondary),
                ),
                const SizedBox(height: 14),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: _memoryCategories
                      .map(
                        (category) => ChoiceChip(
                          label: Text(category),
                          selected: _selectedMemoryCategory == category,
                          onSelected: (_) {
                            setState(() {
                              _selectedMemoryCategory = category;
                            });
                          },
                        ),
                      )
                      .toList(),
                ),
                const SizedBox(height: 12),
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
                  label: 'Memory note',
                  hintText:
                      'Example: If distress escalates, give one calm instruction and wait before speaking again.',
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
                  '4. Stored memory',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 10),
                if ((_memoryContext?.sections ??
                        const <ProfileContextSection>[])
                    .isNotEmpty) ...[
                  const Text(
                    'What Buddy currently remembers',
                    style: TextStyle(color: NeuroColors.textSecondary),
                  ),
                  const SizedBox(height: 10),
                  for (final section in _memoryContext!.sections)
                    _ContextSectionCard(section: section),
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
      padding: const EdgeInsets.all(NeuroColors.spacingMd + 2),
      decoration: BoxDecoration(
        color: NeuroColors.surface,
        borderRadius: BorderRadius.circular(NeuroColors.radiusMd),
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

class _ChoiceSection extends StatelessWidget {
  const _ChoiceSection({
    required this.title,
    required this.options,
    required this.selected,
    required this.onTap,
  });

  final String title;
  final List<String> options;
  final Set<String> selected;
  final ValueChanged<String> onTap;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: options
              .map(
                (option) => FilterChip(
                  label: Text(option),
                  selected: selected.contains(option),
                  onSelected: (_) => onTap(option),
                ),
              )
              .toList(),
        ),
      ],
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

class _ContextSectionCard extends StatelessWidget {
  const _ContextSectionCard({required this.section});

  final ProfileContextSection section;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: NeuroColors.surfaceVariant,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            section.title,
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 8),
          for (final item in section.items) ...[
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('• ', style: TextStyle(fontWeight: FontWeight.w700)),
                Expanded(
                  child: Text(
                    item,
                    style: const TextStyle(color: NeuroColors.textSecondary),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
          ],
        ],
      ),
    );
  }
}
