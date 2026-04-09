class ClinicalResource {
  const ClinicalResource({
    required this.id,
    required this.name,
    required this.resourceType,
    required this.source,
    required this.city,
    this.address,
    this.contact,
    this.instagram,
    this.services,
    this.specialization,
    this.isActive = true,
    this.stale = false,
  });

  final String id;
  final String name;
  final String resourceType;
  final String source;
  final String city;
  final String? address;
  final String? contact;
  final String? instagram;
  final List<String>? services;
  final List<String>? specialization;
  final bool isActive;
  final bool stale;

  factory ClinicalResource.fromJson(String id, Map<String, dynamic> json) {
    List<String>? parseList(dynamic raw) {
      if (raw == null) return null;
      if (raw is List) return raw.map((e) => e.toString()).toList();
      return null;
    }

    return ClinicalResource(
      id: id,
      name: json['name'] as String? ?? '',
      resourceType: json['resource_type'] as String? ?? 'other',
      source: json['source'] as String? ?? 'curated',
      city: json['city'] as String? ?? '',
      address: json['address'] as String?,
      contact: json['contact'] as String?,
      instagram: json['instagram'] as String?,
      services: parseList(json['services']),
      specialization: parseList(json['specialization']),
      isActive: json['is_active'] as bool? ?? true,
      stale: json['stale'] as bool? ?? false,
    );
  }
}
