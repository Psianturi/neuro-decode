import 'dart:convert';
import 'dart:io';

import '../../config/app_config.dart';
import 'clinical_resource.dart';

class ClinicalService {
  Future<List<ClinicalResource>> fetchResources({
    String city = 'jakarta',
    String? resourceType,
    int limit = 100,
  }) async {
    final queryParams = <String, String>{
      'city': city,
      'active_only': 'true',
      'limit': limit.toString(),
      if (resourceType != null) 'resource_type': resourceType,
    };

    final uri = Uri.https(AppConfig.backendUrl, '/clinical-resources', queryParams);

    final client = HttpClient();
    client.connectionTimeout = const Duration(seconds: 10);

    try {
      final request = await client.getUrl(uri);
      final response = await request.close();
      final body = await response.transform(utf8.decoder).join();

      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw HttpException(
          'Request failed (${response.statusCode})',
          uri: uri,
        );
      }

      final decoded = jsonDecode(body);
      final items =
          decoded is List ? decoded : (decoded['resources'] as List? ?? []);
      return items.map<ClinicalResource>((item) {
        final map = item as Map<String, dynamic>;
        final id = map['id'] as String? ?? map['place_id'] as String? ?? '';
        return ClinicalResource.fromJson(id, map);
      }).toList();
    } finally {
      client.close();
    }
  }
}
