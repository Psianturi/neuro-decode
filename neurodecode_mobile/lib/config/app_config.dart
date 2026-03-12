class AppConfig {
  static const String backendUrl =
      'neurodecode-backend-90710068442.asia-southeast1.run.app';
  static const String wsEndpoint = 'wss://$backendUrl/ws/live';

  static Uri liveWsUri({String? profileId}) {
    final trimmedProfileId = profileId?.trim();
    if (trimmedProfileId == null || trimmedProfileId.isEmpty) {
      return Uri.parse(wsEndpoint);
    }

    return Uri.parse(wsEndpoint).replace(
      queryParameters: {
        'profile_id': trimmedProfileId,
      },
    );
  }
}
