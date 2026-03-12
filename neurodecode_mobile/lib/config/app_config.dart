class AppConfig {
  static const String backendUrl =
      'neurodecode-backend-90710068442.asia-southeast1.run.app';
  static const String wsEndpoint = 'wss://$backendUrl/ws/live';

  static Uri liveWsUri({
    required String userId,
    String? profileId,
  }) {
    final trimmedProfileId = profileId?.trim();
    return Uri.parse(wsEndpoint).replace(
      queryParameters: {
        'user_id': userId,
        if (trimmedProfileId != null && trimmedProfileId.isNotEmpty)
          'profile_id': trimmedProfileId,
      },
    );
  }
}
