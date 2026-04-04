import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../theme/app_theme.dart';
import 'clinical_resource.dart';
import 'clinical_service.dart';

class FindHelpScreen extends StatefulWidget {
  const FindHelpScreen({super.key});

  @override
  State<FindHelpScreen> createState() => _FindHelpScreenState();
}

class _FindHelpScreenState extends State<FindHelpScreen> {
  final ClinicalService _service = ClinicalService();

  List<ClinicalResource> _all = [];
  bool _isLoading = false;
  String? _errorMessage;
  String? _selectedType; // null = All

  static const _types = [
    (label: 'All', value: null),
    (label: 'Clinic', value: 'clinic'),
    (label: 'Therapist', value: 'therapist'),
    (label: 'School', value: 'inclusive_school'),
    (label: 'Hospital', value: 'hospital'),
    (label: 'Community', value: 'community'),
  ];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (_isLoading) return;
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });
    try {
      final results = await _service.fetchResources(limit: 100);
      if (!mounted) return;
      setState(() {
        _all = results;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _errorMessage = 'Could not load resources. Please try again.';
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  List<ClinicalResource> get _filtered {
    if (_selectedType == null) return _all;
    return _all
        .where((r) => r.resourceType == _selectedType)
        .toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Find Help'),
        actions: [
          if (_isLoading)
            const Padding(
              padding: EdgeInsets.only(right: NeuroColors.spacingMd),
              child: Center(
                child: SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
              ),
            ),
        ],
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _FilterChipsRow(
            types: _types,
            selected: _selectedType,
            onSelected: (v) => setState(() => _selectedType = v),
          ),
          Expanded(child: _buildBody()),
        ],
      ),
    );
  }

  Widget _buildBody() {
    if (_isLoading && _all.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_errorMessage != null && _all.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(NeuroColors.spacingLg),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.wifi_off_rounded,
                  size: 48,
                  color: Theme.of(context).colorScheme.error.withValues(alpha: 0.6)),
              const SizedBox(height: NeuroColors.spacingMd),
              Text(
                _errorMessage!,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: NeuroColors.spacingMd),
              FilledButton.icon(
                onPressed: _load,
                icon: const Icon(Icons.refresh),
                label: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    final items = _filtered;

    if (items.isEmpty) {
      return Center(
        child: Text(
          'No resources found for this filter.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.separated(
        padding: const EdgeInsets.fromLTRB(
          NeuroColors.spacingMd,
          NeuroColors.spacingSm,
          NeuroColors.spacingMd,
          NeuroColors.spacingLg,
        ),
        itemCount: items.length,
        separatorBuilder: (_, __) =>
            const SizedBox(height: NeuroColors.spacingSm),
        itemBuilder: (ctx, i) => _ResourceCard(resource: items[i]),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Filter chips row
// ─────────────────────────────────────────────────────────────────────────────

typedef _TypeOption = ({String label, String? value});

class _FilterChipsRow extends StatelessWidget {
  const _FilterChipsRow({
    required this.types,
    required this.selected,
    required this.onSelected,
  });

  final List<_TypeOption> types;
  final String? selected;
  final void Function(String?) onSelected;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 48,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(
          horizontal: NeuroColors.spacingMd,
          vertical: NeuroColors.spacingXs,
        ),
        separatorBuilder: (_, __) =>
            const SizedBox(width: NeuroColors.spacingXs),
        itemCount: types.length,
        itemBuilder: (ctx, i) {
          final t = types[i];
          final active = selected == t.value;
          return FilterChip(
            label: Text(t.label),
            selected: active,
            onSelected: (_) => onSelected(t.value),
            showCheckmark: false,
          );
        },
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Resource card
// ─────────────────────────────────────────────────────────────────────────────

class _ResourceCard extends StatelessWidget {
  const _ResourceCard({required this.resource});

  final ClinicalResource resource;

  static const _typeLabels = <String, String>{
    'clinic': 'Clinic',
    'therapist': 'Therapist',
    'hospital': 'Hospital',
    'community': 'Community',
    'inclusive_school': 'Inclusive School',
    'other': 'Other',
  };

  static const _typeColors = <String, Color>{
    'clinic': Color(0xFF4A90C8),
    'therapist': Color(0xFF5BA8A2),
    'hospital': Color(0xFFD35353),
    'community': Color(0xFF8E7CC3),
    'inclusive_school': Color(0xFF5BA87A),
    'other': Color(0xFF78909C),
  };

  @override
  Widget build(BuildContext context) {
    final surface = Theme.of(context).colorScheme.surface;
    final typeLabel =
        _typeLabels[resource.resourceType] ?? resource.resourceType;
    final typeColor =
        _typeColors[resource.resourceType] ?? const Color(0xFF78909C);

    return Container(
      padding: const EdgeInsets.all(NeuroColors.spacingMd),
      decoration: BoxDecoration(
        color: surface,
        borderRadius: BorderRadius.circular(NeuroColors.radiusMd),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Text(
                  resource.name,
                  style: Theme.of(context).textTheme.titleSmall,
                ),
              ),
              const SizedBox(width: NeuroColors.spacingSm),
              _TypeBadge(label: typeLabel, color: typeColor),
            ],
          ),
          if (resource.stale) ...[
            const SizedBox(height: NeuroColors.spacingXs),
            Row(
              children: [
                Icon(Icons.info_outline_rounded,
                    size: 14,
                    color: Theme.of(context)
                        .colorScheme
                        .error
                        .withValues(alpha: 0.7)),
                const SizedBox(width: NeuroColors.spacingXs),
                Text(
                  'Info may be outdated — please verify before visiting.',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Theme.of(context)
                            .colorScheme
                            .error
                            .withValues(alpha: 0.7),
                      ),
                ),
              ],
            ),
          ],
          if (resource.address != null && resource.address!.isNotEmpty) ...[
            const SizedBox(height: NeuroColors.spacingXs),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.location_on_outlined,
                    size: 15,
                    color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5)),
                const SizedBox(width: NeuroColors.spacingXs),
                Expanded(
                  child: Text(
                    resource.address!,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
              ],
            ),
          ],
          if (resource.contact != null && resource.contact!.isNotEmpty) ...[
            const SizedBox(height: NeuroColors.spacingXs),
            GestureDetector(
              onTap: () => _copyPhone(context, resource.contact!),
              child: Row(
                children: [
                  Icon(Icons.phone_outlined,
                      size: 15,
                      color: Theme.of(context).colorScheme.primary),
                  const SizedBox(width: NeuroColors.spacingXs),
                  Text(
                    resource.contact!,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.primary,
                          decoration: TextDecoration.underline,
                        ),
                  ),
                  const SizedBox(width: NeuroColors.spacingXs),
                  Icon(Icons.copy_outlined,
                      size: 12,
                      color: Theme.of(context)
                          .colorScheme
                          .primary
                          .withValues(alpha: 0.6)),
                ],
              ),
            ),
          ],
          if (resource.instagram != null &&
              resource.instagram!.isNotEmpty) ...[
            const SizedBox(height: NeuroColors.spacingXs),
            Row(
              children: [
                Icon(Icons.tag,
                    size: 15,
                    color: Theme.of(context)
                        .colorScheme
                        .onSurface
                        .withValues(alpha: 0.5)),
                const SizedBox(width: NeuroColors.spacingXs),
                Text(
                  resource.instagram!,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ],
          if (resource.services != null && resource.services!.isNotEmpty) ...[
            const SizedBox(height: NeuroColors.spacingXs),
            _ServiceTags(services: resource.services!),
          ],
        ],
      ),
    );
  }

  void _copyPhone(BuildContext context, String phone) {
    Clipboard.setData(ClipboardData(text: phone));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Copied: $phone'),
        duration: const Duration(seconds: 2),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }
}

class _TypeBadge extends StatelessWidget {
  const _TypeBadge({required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: NeuroColors.spacingSm,
        vertical: NeuroColors.spacingXs,
      ),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(NeuroColors.radiusPill),
      ),
      child: Text(
        label,
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: color,
              fontWeight: FontWeight.w600,
            ),
      ),
    );
  }
}

class _ServiceTags extends StatelessWidget {
  const _ServiceTags({required this.services});

  final List<String> services;

  @override
  Widget build(BuildContext context) {
    final visible = services.take(3).toList();
    final overflow = services.length - visible.length;
    return Wrap(
      spacing: NeuroColors.spacingXs,
      runSpacing: NeuroColors.spacingXs,
      children: [
        ...visible.map(
          (s) => Container(
            padding: const EdgeInsets.symmetric(
              horizontal: NeuroColors.spacingXs + 2,
              vertical: 2,
            ),
            decoration: BoxDecoration(
              color: Theme.of(context)
                  .colorScheme
                  .surfaceContainerHighest
                  .withValues(alpha: 0.6),
              borderRadius:
                  BorderRadius.circular(NeuroColors.radiusPill),
            ),
            child: Text(
              s,
              style: Theme.of(context).textTheme.labelSmall,
            ),
          ),
        ),
        if (overflow > 0)
          Container(
            padding: const EdgeInsets.symmetric(
              horizontal: NeuroColors.spacingXs + 2,
              vertical: 2,
            ),
            decoration: BoxDecoration(
              color: Theme.of(context)
                  .colorScheme
                  .surfaceContainerHighest
                  .withValues(alpha: 0.4),
              borderRadius:
                  BorderRadius.circular(NeuroColors.radiusPill),
            ),
            child: Text(
              '+$overflow more',
              style: Theme.of(context).textTheme.labelSmall,
            ),
          ),
      ],
    );
  }
}
