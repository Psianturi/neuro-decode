import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:geocoding/geocoding.dart';
import 'package:geolocator/geolocator.dart';

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
  String? _selectedCity = 'jakarta';
  ({String label, String? value})? _detectedCity;
  bool _isResolvingLocation = false;

  static const _cities = [
    (label: 'All Cities', value: null),
    (label: 'Jakarta', value: 'jakarta'),
    (label: 'Bandung', value: 'bandung'),
    (label: 'Surabaya', value: 'surabaya'),
    (label: 'Medan', value: 'medan'),
    (label: 'Yogyakarta', value: 'yogyakarta'),
    (label: 'Makassar', value: 'makassar'),
    (label: 'Bangkok', value: 'bangkok'),
    (label: 'Singapore', value: 'singapore'),
    (label: 'Kuala Lumpur', value: 'kuala lumpur'),
    (label: 'New York', value: 'new york'),
  ];

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

  List<({String label, String? value})> get _cityOptions {
    final options = List<({String label, String? value})>.from(_cities);
    final detected = _detectedCity;
    if (detected != null) {
      final alreadyExists = options.any(
        (c) =>
            (c.value ?? '').toLowerCase() ==
            (detected.value ?? '').toLowerCase(),
      );
      if (!alreadyExists) {
        options.insert(1, detected);
      }
    }
    return options;
  }

  String _normalizeCity(String raw) {
    var value = raw.trim().toLowerCase();
    value = value.replaceFirst(RegExp(r'^(kota|city of)\s+'), '');
    return value;
  }

  String _prettyCity(String raw) {
    return raw
        .split(RegExp(r'\s+'))
        .where((w) => w.isNotEmpty)
        .map((w) => '${w[0].toUpperCase()}${w.substring(1).toLowerCase()}')
        .join(' ');
  }

  void _showMessage(String text) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(text),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  Future<void> _useCurrentLocation() async {
    if (_isResolvingLocation) return;
    setState(() => _isResolvingLocation = true);

    try {
      final serviceEnabled = await Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) {
        if (!mounted) return;
        _showMessage(
            'Location services are disabled. Please enable GPS first.');
        return;
      }

      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
      if (permission == LocationPermission.denied ||
          permission == LocationPermission.deniedForever) {
        if (!mounted) return;
        _showMessage(
            'Location permission denied. Please select city manually.');
        return;
      }

      final pos = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.low,
        ),
      );

      final placemarks = await placemarkFromCoordinates(
        pos.latitude,
        pos.longitude,
      );

      final first = placemarks.isNotEmpty ? placemarks.first : null;
      final rawCity = first?.locality ??
          first?.subAdministrativeArea ??
          first?.administrativeArea ??
          '';
      final normalizedCity = _normalizeCity(rawCity);

      if (normalizedCity.isEmpty) {
        if (!mounted) return;
        _showMessage('Could not detect city from your current location.');
        return;
      }

      final pretty = _prettyCity(rawCity);
      if (!mounted) return;
      setState(() {
        _detectedCity = (label: 'Detected: $pretty', value: normalizedCity);
        _selectedCity = normalizedCity;
      });
      await _load();
      if (!mounted) return;
      _showMessage('Using current location: $pretty');
    } catch (_) {
      if (!mounted) return;
      _showMessage(
          'Failed to get current location. Please select city manually.');
    } finally {
      if (mounted) {
        setState(() => _isResolvingLocation = false);
      }
    }
  }

  Future<void> _load() async {
    if (_isLoading) return;
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });
    try {
      final results = await _service.fetchResources(
        city: _selectedCity,
        limit: 100,
      );
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
    return _all.where((r) => r.resourceType == _selectedType).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Find Help'),
        actions: [
          if (_isResolvingLocation)
            const Padding(
              padding: EdgeInsets.only(right: NeuroColors.spacingSm),
              child: Center(
                child: SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
              ),
            )
          else
            IconButton(
              onPressed: _useCurrentLocation,
              icon: const Icon(Icons.my_location_outlined),
              tooltip: 'Use current location',
            ),
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
          _CitySelectorRow(
            cities: _cityOptions,
            selected: _selectedCity,
            onSelected: (city) {
              if (_selectedCity == city) return;
              setState(() => _selectedCity = city);
              _load();
            },
          ),
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
                  color: Theme.of(context)
                      .colorScheme
                      .error
                      .withValues(alpha: 0.6)),
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
          _selectedCity == null
              ? 'No resources found for this filter.'
              : 'No resources found in ${_prettyCity(_selectedCity!)} for this filter.',
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
typedef _CityOption = ({String label, String? value});

class _CitySelectorRow extends StatelessWidget {
  const _CitySelectorRow({
    required this.cities,
    required this.selected,
    required this.onSelected,
  });

  final List<_CityOption> cities;
  final String? selected;
  final void Function(String?) onSelected;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        NeuroColors.spacingMd,
        NeuroColors.spacingSm,
        NeuroColors.spacingMd,
        0,
      ),
      child: Row(
        children: [
          Icon(
            Icons.location_on_outlined,
            size: 18,
            color:
                Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
          ),
          const SizedBox(width: NeuroColors.spacingXs),
          const Text('City:'),
          const SizedBox(width: NeuroColors.spacingXs),
          Expanded(
            child: DropdownButtonHideUnderline(
              child: DropdownButton<String?>(
                value: selected,
                isExpanded: true,
                items: cities
                    .map(
                      (c) => DropdownMenuItem<String?>(
                        value: c.value,
                        child: Text(c.label),
                      ),
                    )
                    .toList(),
                onChanged: onSelected,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

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
    final sourceKey = resource.source.toLowerCase();
    final sourceLabel = sourceKey == 'live_search' ? 'Live Search' : 'Curated';
    final sourceColor = sourceKey == 'live_search'
        ? const Color(0xFF8E7CC3)
        : const Color(0xFF5BA87A);

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
          const SizedBox(height: NeuroColors.spacingXs),
          _SourceBadge(label: sourceLabel, color: sourceColor),
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
                    color: Theme.of(context)
                        .colorScheme
                        .onSurface
                        .withValues(alpha: 0.5)),
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
                      size: 15, color: Theme.of(context).colorScheme.primary),
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
          if (resource.instagram != null && resource.instagram!.isNotEmpty) ...[
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

class _SourceBadge extends StatelessWidget {
  const _SourceBadge({required this.label, required this.color});

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
        color: color.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(NeuroColors.radiusPill),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.verified_outlined, size: 12, color: color),
          const SizedBox(width: 4),
          Text(
            'Source: $label',
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: color,
                  fontWeight: FontWeight.w600,
                ),
          ),
        ],
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
              borderRadius: BorderRadius.circular(NeuroColors.radiusPill),
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
              borderRadius: BorderRadius.circular(NeuroColors.radiusPill),
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
