import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/foundation.dart';
import 'package:flutter_sound/flutter_sound.dart';
import 'package:logger/logger.dart';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../../config/app_config.dart';
import '../../theme/app_theme.dart';
import 'observer_panel_sheet.dart';

enum AgentState { idle, connecting, listening, thinking, speaking, error }

class LiveAgentScreen extends StatefulWidget {
  const LiveAgentScreen({
    super.key,
    required this.cameras,
    required this.observerEnabled,
    required this.userId,
    this.profileId,
  });

  final List<CameraDescription> cameras;
  final bool observerEnabled;
  final String userId;
  final String? profileId;

  @override
  State<LiveAgentScreen> createState() => _LiveAgentScreenState();
}

class _LiveAgentScreenState extends State<LiveAgentScreen> {
  static const MethodChannel _nativeAudioChannel =
      MethodChannel('neurodecode/live_audio');
  static const int _geminiOutputSampleRate = 24000;
  static const int _geminiOutputChannels = 1;
  static const int _maxPlaybackChunkBytes = 5760;
  static const int _audioFlushThresholdBytes =
      5760; // ~120 ms @24kHz mono PCM16
  static const int _audioPrebufferBytes = 11520; // ~240 ms @24kHz mono PCM16
  static const int _audioDropFrameBytes = 48000; // ~1 second @24kHz mono PCM16
  static const Duration _audioFlushInterval = Duration(milliseconds: 45);
  static const int _minTurnAudioBytes = 8000;
  static const Duration _minTurnDuration = Duration(milliseconds: 350);
  static const Duration _playerIdleCloseDelay = Duration(seconds: 8);

  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _wsSub;
  AgentState _state = AgentState.idle;

  final AudioRecorder _recorder = AudioRecorder();
  StreamSubscription<Uint8List>? _micStreamSub;
  bool _isMicActive = false;
  final FlutterSoundPlayer _soundPlayer =
      FlutterSoundPlayer(logLevel: Level.warning);
  final bool _preferNativeAndroidPcm =
      defaultTargetPlatform == TargetPlatform.android;
  bool _nativeAndroidPcmAvailable = true;
  bool _isPlayerReady = false;
  bool _isPlayerStreamOpen = false;
  bool _geminiTurnComplete = true;
  Future<void>? _feedChain;
  static const int _playerBufferSize = 8192;
  final BytesBuilder _pendingPcmBuffer = BytesBuilder(copy: false);
  Timer? _audioFlushTimer;
  Timer? _playerIdleTimer;
  int _playerSampleRate = _geminiOutputSampleRate;
  CameraController? _cameraController;
  Timer? _visionTimer;
  bool _isCapturingFrame = false;
  bool _isCleaningUp = false;
  bool _isManualClose = false;
  bool _backendFatalError = false;
  bool _profileMemoryLoaded = false;
  String? _profileMemoryProfileId;
  int _profileMemoryLineCount = 0;
  List<String> _profileMemoryCues = const <String>[];
  bool _cameraPreviewPaused = false;
  Offset _cameraPreviewOffset = const Offset(0, 0);
  int _currentTurnAudioBytes = 0;
  DateTime? _currentTurnStartedAt;

  bool _seenTranscriptOutInCurrentTurn = false;
  DateTime? _lastGeminiChunkAt;
  DateTime? _lastUserChunkAt;
  String _pendingGeminiTranscript = '';
  final List<String> _debugLog = [];
  final List<ObserverEvent> _observerEvents = [];

  final List<Map<String, String>> _transcriptLog = [];
  final ScrollController _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    _initSoundPlayer();
    _checkPermissions();
    _initCamera();
    _connect();
  }

  Future<void> _initSoundPlayer() async {
    if (_preferNativeAndroidPcm) {
      _isPlayerReady = true;
      _logDebug('player_event', 'Native Android PCM player selected');
      return;
    }
    await _soundPlayer.openPlayer();
    _isPlayerReady = true;
    _logDebug('player_event', 'FlutterSoundPlayer opened');
  }

  Future<void> _checkPermissions() async {
    try {
      await [Permission.microphone, Permission.camera].request();
    } catch (_) {}
  }

  Future<void> _initCamera() async {
    if (!widget.observerEnabled || widget.cameras.isEmpty) {
      _logDebug('camera_event', 'observer disabled or camera unavailable');
      return;
    }

    try {
      final controller = CameraController(
        widget.cameras.first,
        ResolutionPreset.low,
        enableAudio: false,
      );
      await controller.initialize();
      if (!mounted) {
        await controller.dispose();
        return;
      }
      setState(() {
        _cameraController = controller;
      });
      _logDebug('camera_event', 'preview initialized');
      _startVisionLoop();
    } catch (e) {
      _logDebug('camera_event', 'failed: $e');
    }
  }

  Future<void> _retryCameraInit() async {
    _stopVisionLoop();
    final old = _cameraController;
    _cameraController = null;
    await old?.dispose();
    if (!mounted) return;
    setState(() {});
    await _initCamera();
  }

  bool get _isConnected =>
      _channel != null && _wsSub != null && _state != AgentState.error;

  bool get _shouldStreamVisionContext =>
      _isConnected &&
      !_isMicActive &&
      _state != AgentState.thinking &&
      _state != AgentState.speaking &&
      !_cameraPreviewPaused;

  void _setStateLabel(AgentState next) {
    if (_state == next) return;
    _logDebug('state_change', '$_state \u2192 $next');
    if (!mounted) return;
    setState(() {
      _state = next;
    });
  }

  void _connect() {
    if (_isConnected) return;
    _isManualClose = false;
    _backendFatalError = false;
    _setStateLabel(AgentState.connecting);
    final wsUri = AppConfig.liveWsUri(
      userId: widget.userId,
      profileId: widget.profileId,
    );
    _logDebug('ws_event', 'connecting $wsUri');
    try {
      _channel = WebSocketChannel.connect(wsUri);
      _wsSub = _channel!.stream.listen(
        _onMessageReceived,
        onDone: () {
          _logDebug('ws_event', 'connection closed (onDone)');
          _handleSocketClosed(manual: false);
          if (!_isManualClose && !_backendFatalError && mounted) {
            _logDebug('ws_event', 'auto-reconnecting in 3s...');
            _addLog('System', 'Connection lost. Reconnecting...');
            Future.delayed(const Duration(seconds: 3), () {
              if (mounted &&
                  !_isConnected &&
                  !_isManualClose &&
                  !_backendFatalError) {
                _connect();
              }
            });
          }
        },
        onError: (error) {
          _setStateLabel(AgentState.error);
          _addLog('Error', 'Connection error: $error');
          _logDebug('ws_event', 'error: $error');
          _handleSocketClosed(manual: false);
          if (!_isManualClose && !_backendFatalError && mounted) {
            _logDebug('ws_event', 'auto-reconnecting in 3s...');
            Future.delayed(const Duration(seconds: 3), () {
              if (mounted &&
                  !_isConnected &&
                  !_isManualClose &&
                  !_backendFatalError) {
                _connect();
              }
            });
          }
        },
      );

      if (!mounted) return;
      _setStateLabel(AgentState.idle);
      _addLog('System', 'Connected to NeuroDecode agent.');
      _logDebug('ws_event', 'connected');
    } catch (e) {
      _setStateLabel(AgentState.error);
      _addLog('System', 'Failed to connect: $e');
      _logDebug('ws_event', 'failed: $e');
    }
  }

  Future<void> _disconnect() async {
    _isManualClose = true;
    _stopVisionLoop();
    _stopMicStreamSync();
    final currentChannel = _channel;
    if (currentChannel != null) {
      try {
        currentChannel.sink.add(jsonEncode({'type': 'close'}));
        _logDebug('ws_event', 'close message sent');
        await Future.delayed(const Duration(milliseconds: 180));
      } catch (e) {
        _logDebug('ws_event', 'close message failed: $e');
      }
    }
    _handleSocketClosed(manual: true);
  }

  void _openObserverPanel() {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (_) => ObserverPanelSheet(
        events: _observerEvents,
      ),
    );
  }

  void _onMessageReceived(dynamic message) {
    if (!mounted || _isCleaningUp) {
      return;
    }
    try {
      final data = jsonDecode(message as String);
      final type = data['type'];
      final isHighFrequencyMessage = type == 'model_audio' ||
          type == 'transcript_in' ||
          type == 'transcript_out';
      if (!isHighFrequencyMessage) {
        _logDebug('ws_event', 'message type=$type');
      }

      if (type == 'transcript_in') {
        final text = (data['text'] ?? '').toString();
        if (_shouldDisplayUserTranscript(text)) {
          _appendUserChunk(text);
        }
        return;
      }

      if (type == 'transcript_out') {
        _setStateLabel(AgentState.speaking);
        _seenTranscriptOutInCurrentTurn = true;
        final text = (data['text'] ?? '').toString();
        if (text.isNotEmpty) {
          _bufferGeminiTranscript(text);
        }
        return;
      }

      if (type == 'model_text') {
        if (_seenTranscriptOutInCurrentTurn) {
          return;
        }
        _setStateLabel(AgentState.speaking);
        final text = (data['text'] ?? data['data'] ?? '').toString();
        if (text.isNotEmpty) {
          _appendGeminiChunk(text);
        }
        return;
      }

      if (type == 'model_audio') {
        _setStateLabel(AgentState.speaking);
        _geminiTurnComplete = false;
        _cancelPlayerIdleClose();
        final b64 = (data['data_b64'] ?? '').toString();
        final mimeType = (data['mime_type'] ?? '').toString();
        final nextSampleRate =
            _sampleRateFromMimeType(mimeType) ?? _geminiOutputSampleRate;
        if (nextSampleRate != _playerSampleRate) {
          _playerSampleRate = nextSampleRate;
          _stopPlayerStreamNow();
          _logDebug(
              'player_event', 'sample rate updated to ${_playerSampleRate}Hz');
        }
        // PATCH: Clear buffer at the start of a new turn (first model_audio after turn complete)
        if (_pendingPcmBuffer.length > 0 && _lastGeminiChunkAt == null) {
          _logDebug('audio_patch', 'Clearing buffer at new turn start');
          _clearPendingAudio();
        }
        if (b64.isNotEmpty) {
          _queueAudioChunk(Uint8List.fromList(base64Decode(b64)));
        }
        _lastGeminiChunkAt = DateTime.now();
        return;
      }

      if (type == 'model_audio_end') {
        _logDebug(
            'audio_end', 'turn complete, delaying 600ms for buffer drain');
        _geminiTurnComplete = true;
        _seenTranscriptOutInCurrentTurn = false;
        _lastGeminiChunkAt = null;
        _lastUserChunkAt = null;
        _commitPendingGeminiTranscript();
        _flushPendingAudio();
        // Delay state change so OS audio buffer can drain
        Future.delayed(const Duration(milliseconds: 600), () {
          if (mounted && _geminiTurnComplete) {
            _setStateLabel(AgentState.idle);
            if (!(_preferNativeAndroidPcm && _nativeAndroidPcmAvailable)) {
              _schedulePlayerIdleClose();
            }
          }
        });
        return;
      }

      if (type == 'interrupted') {
        _stopPlayerStreamNow();
        _geminiTurnComplete = true;
        _lastUserChunkAt = null;
        _pendingGeminiTranscript = '';
        _addLog('System', 'Gemini response interrupted.');
        _logDebug('player_event', 'interrupted, stream stopped');
        _setStateLabel(AgentState.idle);
        return;
      }

      if (type == 'error') {
        _backendFatalError = true;
        _setStateLabel(AgentState.error);
        final text = (data['message'] ?? 'Unknown backend error').toString();
        _addLog('Error', text);
        _channel?.sink.close();
        return;
      }

      if (type == 'observer_note') {
        final raw = (data['text'] ?? '').toString();
        final text = _sanitizeObserverNote(raw);
        if (text.isNotEmpty) {
          _addObserverEvent(
            text: text,
            confidence: ObserverConfidence.medium,
          );
        }
        return;
      }

      if (type == 'profile_memory_status') {
        final loaded = (data['loaded'] ?? false) == true;
        if (loaded) {
          final profileId = (data['profile_id'] ?? '').toString();
          final lineCountRaw = data['line_count'];
          final lineCount = lineCountRaw is int
              ? lineCountRaw
              : int.tryParse((lineCountRaw ?? '0').toString()) ?? 0;
          final cuesRaw = data['cues'];
          final cues = cuesRaw is List
              ? cuesRaw
                  .map((item) => item.toString().trim())
                  .where((item) => item.isNotEmpty)
                  .toList()
              : <String>[];
          if (mounted) {
            setState(() {
              _profileMemoryLoaded = true;
              _profileMemoryProfileId = profileId;
              _profileMemoryLineCount = lineCount;
              _profileMemoryCues = cues;
            });
          }
          _addLog(
            'System',
            'Profile memory active for $profileId ($lineCount context lines).',
          );
          if (cues.isNotEmpty) {
            _addLog(
              'System',
              'Memory cues: ${cues.join(' | ')}',
            );
          }
        }
        return;
      }
    } catch (e) {
      _logDebug('ws_event', 'ERROR processing message: $e');
      _addLog('Error', 'Failed to process message: $e');
    }
  }

  String _sanitizeObserverNote(String input) {
    var out = input.trim();
    out = out.replaceFirst(
      RegExp(r'^\[(Audio|Visual) Observer Note\]\s*', caseSensitive: false),
      '',
    );
    return out.trim();
  }

  String _sanitizeAgentText(String input) {
    var out = input.trim();
    out = out.replaceFirst(
      RegExp(r'^\[(Audio|Visual) Observer Note\]\s*', caseSensitive: false),
      '',
    );
    out = out.replaceFirst(
      RegExp(
        r'^INTERNAL SENSOR NOTE \(PRIVATE CONTEXT - DO NOT REPEAT VERBATIM TO USER\):\s*',
        caseSensitive: false,
      ),
      '',
    );
    out = out.replaceFirst(
      RegExp(r'^translate\s*', caseSensitive: false),
      '',
    );
    return out.trim();
  }

  void _addObserverEvent({
    required String text,
    required ObserverConfidence confidence,
  }) {
    if (!mounted) return;
    setState(() {
      _observerEvents.add(
        ObserverEvent(
          timestamp: DateTime.now(),
          text: text,
          confidence: confidence,
        ),
      );
      if (_observerEvents.length > 100) {
        _observerEvents.removeRange(0, _observerEvents.length - 100);
      }
    });
  }

  void _toggleMic() async {
    _logDebug('mic_toggle',
        'START: mic=$_isMicActive state=$_state connected=$_isConnected');
    if (!_isConnected) {
      _addLog('System', 'Agent is not connected yet. Reconnecting...');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Agent disconnected. Reconnecting...')),
        );
      }
      _connect();
      return;
    }

    // Guard: prevent toggle while AI is thinking
    if (!_isMicActive && _state == AgentState.thinking) {
      _logDebug('mic_toggle', 'BLOCKED: AI is thinking');
      return;
    }

    if (_isMicActive) {
      _logDebug('mic_toggle', 'STOPPING mic stream');
      await _stopMicStream();
    } else {
      // Barge-in: stop Gemini audio if it's speaking when user starts talking
      if (_state == AgentState.speaking) {
        _stopPlayerStreamNow();
        _geminiTurnComplete = true;
        _logDebug('barge_in', 'user interrupted Gemini, audio stopped');
      }
      _logDebug('mic_toggle', 'STARTING mic stream');
      await _startMicStream();
    }
    _logDebug('mic_toggle', 'END: mic=$_isMicActive state=$_state');
  }

  // ── Vision Loop: periodic camera frame capture ──

  void _startVisionLoop() {
    if (_visionTimer != null) return;
    _visionTimer = Timer.periodic(const Duration(seconds: 3), (_) {
      _captureAndSendFrame();
    });
    _logDebug('vision', 'vision loop started (every 3s)');
  }

  void _stopVisionLoop() {
    _visionTimer?.cancel();
    _visionTimer = null;
  }

  Future<void> _captureAndSendFrame() async {
    final controller = _cameraController;
    if (controller == null || !controller.value.isInitialized) return;
    if (!_shouldStreamVisionContext || _channel == null) return;
    if (_isCapturingFrame) return;

    _isCapturingFrame = true;
    try {
      final xFile = await controller.takePicture();
      final bytes = await xFile.readAsBytes();
      final b64 = base64Encode(bytes);

      _channel!.sink.add(jsonEncode({
        'type': 'image',
        'data_b64': b64,
        'mime_type': 'image/jpeg',
      }));
      _logDebug('vision', 'frame sent (${bytes.length} bytes)');
    } catch (e) {
      _logDebug('vision', 'capture failed: $e');
    } finally {
      _isCapturingFrame = false;
    }
  }

  Future<void> _startMicStream() async {
    if (_isMicActive || !_isConnected) return;
    if (!await _recorder.hasPermission()) return;

    const config = RecordConfig(
      encoder: AudioEncoder.pcm16bits,
      sampleRate: 16000,
      numChannels: 1,
    );

    final stream = await _recorder.startStream(config);
    _currentTurnAudioBytes = 0;
    _currentTurnStartedAt = DateTime.now();
    if (mounted) {
      setState(() {
        _isMicActive = true;
      });
    }
    _setStateLabel(AgentState.listening);
    _logDebug('mic_event', 'toggle ON — streaming started');

    _micStreamSub = stream.listen((chunk) {
      final currentChannel = _channel;
      if (!_isConnected || currentChannel == null) return;

      final payload = {
        'type': 'audio',
        'data_b64': base64Encode(chunk),
        'mime_type': 'audio/pcm;rate=16000',
      };
      _currentTurnAudioBytes += chunk.length;
      currentChannel.sink.add(jsonEncode(payload));
    });
  }

  /// Synchronous cleanup variant used by _handleSocketClosed / dispose.
  void _stopMicStreamSync() {
    if (!_isMicActive) return;
    _micStreamSub?.cancel();
    _micStreamSub = null;
    _recorder.stop();
    if (mounted) {
      setState(() {
        _isMicActive = false;
      });
    }
  }

  Future<void> _stopMicStream() async {
    if (!_isMicActive) return;

    await _micStreamSub?.cancel();
    _micStreamSub = null;
    await _recorder.stop();
    _logDebug('mic_event', 'toggle OFF — streaming stopped');

    final turnDuration = _currentTurnStartedAt == null
        ? Duration.zero
        : DateTime.now().difference(_currentTurnStartedAt!);
    final shouldIgnoreShortTurn = _currentTurnAudioBytes < _minTurnAudioBytes ||
        turnDuration < _minTurnDuration;

    if (_isConnected && _channel != null && !shouldIgnoreShortTurn) {
      _channel!.sink.add(
        jsonEncode(
          {
            'type': 'audio_stream_end',
          },
        ),
      );
      _logDebug('turn_event', 'audio_stream_end sent');
    } else if (shouldIgnoreShortTurn) {
      _logDebug(
        'turn_event',
        'short turn ignored ($_currentTurnAudioBytes bytes, ${turnDuration.inMilliseconds}ms)',
      );
    }

    _currentTurnAudioBytes = 0;
    _currentTurnStartedAt = null;

    if (mounted) {
      setState(() {
        _isMicActive = false;
      });
    }
    _setStateLabel(
        shouldIgnoreShortTurn ? AgentState.idle : AgentState.thinking);
  }

  void _feedAudio(Uint8List pcm) {
    // Chain feed operations to ensure sequential execution.
    _feedChain = (_feedChain ?? Future.value())
        .then((_) => _doFeedAudio(pcm))
        .catchError((e) => _logDebug('player_event', 'feed error: $e'));
  }

  void _queueAudioChunk(Uint8List pcm) {
    if (pcm.isEmpty) return;

    // PATCH: Drop frame policy if buffer is too long (>2 seconds of audio)
    if (_pendingPcmBuffer.length > _audioDropFrameBytes) {
      _logDebug('audio_patch',
          'Drop frame: buffer >2 seconds, clearing ${_pendingPcmBuffer.length} bytes');
      _clearPendingAudio();
    }

    _pendingPcmBuffer.add(pcm);

    // PATCH: Pre-buffer at least 0.5 seconds before playback
    if (!_isPlayerStreamOpen &&
        _pendingPcmBuffer.length < _audioPrebufferBytes) {
      _logDebug(
          'audio_patch', 'Pre-buffering: ${_pendingPcmBuffer.length} bytes');
      // Wait until buffer is sufficient before starting playback
      return;
    }

    if (_pendingPcmBuffer.length >= _audioFlushThresholdBytes) {
      _logDebug('audio_patch',
          'Flush: buffer >= threshold (${_pendingPcmBuffer.length} bytes)');
      _flushPendingAudio();
      return;
    }

    _audioFlushTimer ??= Timer(_audioFlushInterval, () {
      _audioFlushTimer = null;
      _logDebug(
          'audio_patch', 'Flush: interval (${_pendingPcmBuffer.length} bytes)');
      _flushPendingAudio();
    });
  }

  void _flushPendingAudio() {
    _audioFlushTimer?.cancel();
    _audioFlushTimer = null;
    if (_pendingPcmBuffer.length == 0) return;

    final pcm = _pendingPcmBuffer.takeBytes();
    for (final chunk in _splitPlaybackChunks(pcm)) {
      _feedAudio(chunk);
    }
  }

  Iterable<Uint8List> _splitPlaybackChunks(Uint8List pcm) sync* {
    if (pcm.isEmpty) {
      return;
    }

    if (pcm.length <= _maxPlaybackChunkBytes) {
      yield pcm;
      return;
    }

    for (var offset = 0;
        offset < pcm.length;
        offset += _maxPlaybackChunkBytes) {
      final end =
          (offset + _maxPlaybackChunkBytes).clamp(0, pcm.length).toInt();
      yield Uint8List.sublistView(pcm, offset, end);
    }
  }

  void _cancelPlayerIdleClose() {
    _playerIdleTimer?.cancel();
    _playerIdleTimer = null;
  }

  void _schedulePlayerIdleClose() {
    _cancelPlayerIdleClose();
    _playerIdleTimer = Timer(_playerIdleCloseDelay, () {
      if (!_isMicActive && _geminiTurnComplete) {
        _closePlayerStream();
      }
    });
  }

  void _clearPendingAudio() {
    _audioFlushTimer?.cancel();
    _audioFlushTimer = null;
    if (_pendingPcmBuffer.length == 0) return;
    _pendingPcmBuffer.takeBytes();
  }

  Future<void> _doFeedAudio(Uint8List pcm) async {
    if (!_isPlayerReady) return;
    _cancelPlayerIdleClose();
    if (_preferNativeAndroidPcm && _nativeAndroidPcmAvailable) {
      await _feedNativeAndroidPcm(pcm);
      return;
    }
    if (!_isPlayerStreamOpen) {
      await _soundPlayer.startPlayerFromStream(
        codec: Codec.pcm16,
        interleaved: true,
        sampleRate: _playerSampleRate,
        numChannels: _geminiOutputChannels,
        bufferSize: _playerBufferSize,
      );
      _isPlayerStreamOpen = true;
      _logDebug(
        'player_event',
        'PCM stream opened at ${_playerSampleRate}Hz (channels: $_geminiOutputChannels, codec: pcm16)',
      );
    }
    await _soundPlayer.feedUint8FromStream(pcm);
  }

  Future<void> _feedNativeAndroidPcm(Uint8List pcm) async {
    if (!_isPlayerStreamOpen) {
      try {
        await _nativeAudioChannel.invokeMethod<void>('initPlayer', {
          'sampleRate': _playerSampleRate,
          'channelCount': _geminiOutputChannels,
          'bufferBytes': _playerBufferSize,
        });
        _isPlayerStreamOpen = true;
        _logDebug(
          'player_event',
          'Native PCM stream opened at ${_playerSampleRate}Hz (channels: $_geminiOutputChannels)',
        );
      } on PlatformException catch (e) {
        _nativeAndroidPcmAvailable = false;
        _logDebug('player_event',
            'Native PCM init failed, falling back: ${e.message}');
        await _soundPlayer.openPlayer();
        _isPlayerReady = true;
        await _doFeedAudio(pcm);
        return;
      }
    }
    try {
      await _nativeAudioChannel.invokeMethod<void>('writePcm', {
        'bytes': pcm,
      });
    } on PlatformException catch (e) {
      _nativeAndroidPcmAvailable = false;
      _isPlayerStreamOpen = false;
      _logDebug('player_event',
          'Native PCM write failed, falling back: ${e.message}');
      await _soundPlayer.openPlayer();
      _isPlayerReady = true;
      await _doFeedAudio(pcm);
    }
  }

  void _closePlayerStream() {
    _cancelPlayerIdleClose();
    _flushPendingAudio();
    if (_isPlayerStreamOpen) {
      if (_preferNativeAndroidPcm && _nativeAndroidPcmAvailable) {
        _logDebug(
            'player_event', 'native PCM player kept alive across idle turn');
        return;
      } else {
        _soundPlayer.stopPlayer();
      }
      _isPlayerStreamOpen = false;
      _feedChain = null;
      _logDebug('player_event', 'PCM stream closed');
    }
  }

  void _stopPlayerStreamNow() {
    _cancelPlayerIdleClose();
    _clearPendingAudio();
    if (_isPlayerStreamOpen) {
      if (_preferNativeAndroidPcm && _nativeAndroidPcmAvailable) {
        _nativeAudioChannel.invokeMethod<void>('flushPlayer');
        _feedChain = null;
        _logDebug('player_event', 'native PCM queue flushed');
        return;
      } else {
        _soundPlayer.stopPlayer();
      }
      _isPlayerStreamOpen = false;
      _feedChain = null;
    }
  }

  void _logDebug(String tag, String msg) {
    final ts = DateFormat('HH:mm:ss').format(DateTime.now());
    // Skip setState for high-frequency audio tags to avoid UI thread contention
    if (tag == 'audio_patch') {
      _debugLog.add('[$ts] $tag: $msg');
      if (_debugLog.length > 200) {
        _debugLog.removeRange(0, _debugLog.length - 200);
      }
      return;
    }
    if (!mounted) return;
    setState(() {
      _debugLog.add('[$ts] $tag: $msg');
      if (_debugLog.length > 200) {
        _debugLog.removeRange(0, _debugLog.length - 200);
      }
    });
  }

  int? _sampleRateFromMimeType(String mimeType) {
    final match =
        RegExp(r'rate=(\d+)', caseSensitive: false).firstMatch(mimeType);
    if (match == null) return null;
    return int.tryParse(match.group(1)!);
  }

  bool _shouldDisplayUserTranscript(String text) {
    final normalized = text.trim();
    if (normalized.isEmpty) {
      return false;
    }

    final lowered = normalized.toLowerCase();
    if (lowered == '[noise]' ||
        lowered == '[silence]' ||
        lowered == '[inaudible]' ||
        lowered == '<noise>' ||
        lowered == '<silence>' ||
        lowered == '<inaudible>') {
      return false;
    }

    if (RegExp(r'^[.\s]+$').hasMatch(normalized)) {
      return false;
    }

    return true;
  }

  void _appendGeminiChunk(String chunk) {
    final normalized = _sanitizeAgentText(chunk);
    if (normalized.isEmpty || !mounted) return;

    final now = DateTime.now();
    final shouldMerge = _transcriptLog.isNotEmpty &&
        _transcriptLog.last['sender'] == 'Gemini' &&
        _lastGeminiChunkAt != null &&
        now.difference(_lastGeminiChunkAt!) <
            const Duration(milliseconds: 1200);

    setState(() {
      if (shouldMerge) {
        final previous = _transcriptLog.last['text'] ?? '';
        final needsSpace = previous.isNotEmpty &&
            !previous.endsWith(' ') &&
            !RegExp(r'^[,.;:!?)]').hasMatch(normalized);
        final merged =
            needsSpace ? '$previous $normalized' : '$previous$normalized';
        _transcriptLog[_transcriptLog.length - 1] = {
          'sender': 'Gemini',
          'text': merged,
        };
      } else {
        _transcriptLog.add({'sender': 'Gemini', 'text': normalized});
      }
    });

    _lastGeminiChunkAt = now;
    _scrollToBottom();
  }

  void _bufferGeminiTranscript(String chunk) {
    final normalized = _sanitizeAgentText(chunk);
    if (normalized.isEmpty) return;

    final needsSpace = _pendingGeminiTranscript.isNotEmpty &&
        !_pendingGeminiTranscript.endsWith(' ') &&
        !RegExp(r'^[,.;:!?)]').hasMatch(normalized);
    _pendingGeminiTranscript = needsSpace
        ? '$_pendingGeminiTranscript $normalized'
        : '$_pendingGeminiTranscript$normalized';
  }

  void _commitPendingGeminiTranscript() {
    final pending = _pendingGeminiTranscript.trim();
    _pendingGeminiTranscript = '';
    if (pending.isEmpty) return;
    _appendGeminiChunk(pending);
  }

  void _appendUserChunk(String chunk) {
    final normalized = chunk.trim();
    if (normalized.isEmpty || !mounted) return;

    final now = DateTime.now();
    final shouldMerge = _transcriptLog.isNotEmpty &&
        _transcriptLog.last['sender'] == 'You' &&
        _lastUserChunkAt != null &&
        now.difference(_lastUserChunkAt!) < const Duration(milliseconds: 1500);

    setState(() {
      if (shouldMerge) {
        final previous = _transcriptLog.last['text'] ?? '';
        final needsSpace = previous.isNotEmpty &&
            !previous.endsWith(' ') &&
            !RegExp(r'^[,.;:!?)]').hasMatch(normalized);
        final merged =
            needsSpace ? '$previous $normalized' : '$previous$normalized';
        _transcriptLog[_transcriptLog.length - 1] = {
          'sender': 'You',
          'text': merged,
        };
      } else {
        _transcriptLog.add({'sender': 'You', 'text': normalized});
      }
    });

    _lastUserChunkAt = now;
    _scrollToBottom();
  }

  void _addLog(String sender, String message) {
    if (!mounted || message.isEmpty) return;
    setState(() {
      _transcriptLog.add({'sender': sender, 'text': message});
    });
    _scrollToBottom();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || _isCleaningUp) {
        return;
      }
      try {
        if (_scrollController.hasClients) {
          _scrollController.animateTo(
            _scrollController.position.maxScrollExtent,
            duration: const Duration(milliseconds: 300),
            curve: Curves.easeOut,
          );
        }
      } catch (_) {
        // Ignore late scroll callbacks after dispose.
      }
    });
  }

  void _handleSocketClosed({required bool manual}) {
    if (_isCleaningUp) return;
    _isCleaningUp = true;

    _stopVisionLoop();
    _stopMicStreamSync();

    // Cancel subscription BEFORE closing sink to prevent onDone re-fire.
    final sub = _wsSub;
    _wsSub = null;
    sub?.cancel();

    final ch = _channel;
    _channel = null;
    ch?.sink.close();

    _stopPlayerStreamNow();
    _geminiTurnComplete = true;
    _seenTranscriptOutInCurrentTurn = false;
    _lastGeminiChunkAt = null;
    _lastUserChunkAt = null;
    _pendingGeminiTranscript = '';
    _profileMemoryLoaded = false;
    _profileMemoryProfileId = null;
    _profileMemoryLineCount = 0;
    _profileMemoryCues = const <String>[];

    if (mounted) {
      if (!_backendFatalError) {
        _setStateLabel(AgentState.idle);
      }
      if (manual) {
        _addLog('System', 'Session terminated.');
      }
    }
    _isCleaningUp = false;
  }

  @override
  void dispose() {
    // Inline cleanup without calling _handleSocketClosed to avoid setState during dispose.
    _isCleaningUp = true;
    _stopVisionLoop();
    _stopMicStreamSync();
    _wsSub?.cancel();
    _wsSub = null;
    _channel?.sink.close();
    _channel = null;
    _stopPlayerStreamNow();
    _audioFlushTimer?.cancel();
    _playerIdleTimer?.cancel();
    if (_preferNativeAndroidPcm && _nativeAndroidPcmAvailable) {
      _nativeAudioChannel.invokeMethod<void>('releasePlayer');
    } else {
      _soundPlayer.closePlayer();
    }
    _scrollController.dispose();
    _cameraController?.dispose();
    _recorder.dispose();
    super.dispose();
  }

  String get _stateLabel {
    switch (_state) {
      case AgentState.connecting:
        return 'CONNECTING';
      case AgentState.listening:
        return 'LISTENING';
      case AgentState.thinking:
        return 'THINKING';
      case AgentState.speaking:
        return 'SPEAKING';
      case AgentState.error:
        return 'ERROR';
      case AgentState.idle:
        return 'IDLE';
    }
  }

  Color _getStateColor(AgentState state) {
    switch (state) {
      case AgentState.connecting:
        return Colors.orange;
      case AgentState.listening:
        return Colors.blue;
      case AgentState.thinking:
        return Colors.purple;
      case AgentState.speaking:
        return Colors.green;
      case AgentState.error:
        return Colors.red;
      case AgentState.idle:
        return Colors.grey;
    }
  }

  void _openDebugLog() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Debug Log'),
        content: SizedBox(
          width: double.maxFinite,
          height: 400,
          child: ListView.builder(
            itemCount: _debugLog.length,
            itemBuilder: (_, i) => Padding(
              padding: const EdgeInsets.symmetric(vertical: 1),
              child: Text(
                _debugLog[i],
                style: const TextStyle(fontFamily: 'monospace', fontSize: 10),
              ),
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () {
              setState(() => _debugLog.clear());
              Navigator.pop(ctx);
            },
            child: const Text('Clear'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final navigator = Navigator.of(context);
    return PopScope(
      canPop: !_isConnected,
      onPopInvokedWithResult: (didPop, _) async {
        if (didPop) {
          return;
        }
        if (_isConnected) {
          await _disconnect();
        }
        if (mounted) {
          navigator.pop();
        }
      },
      child: Scaffold(
        appBar: AppBar(
          leading: IconButton(
            icon: const Icon(Icons.arrow_back),
            onPressed: () async {
              if (_isConnected) {
                await _disconnect();
              }
              if (mounted) {
                navigator.maybePop();
              }
            },
          ),
          title: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Live Session'),
              Text(
                _stateLabel,
                style: TextStyle(
                  fontSize: 12,
                  color: _getStateColor(_state),
                ),
              ),
              if (_profileMemoryLoaded)
                Container(
                  margin: const EdgeInsets.only(top: 2),
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: NeuroColors.secondary.withValues(alpha: 0.95),
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    'Memory Active${_profileMemoryProfileId != null ? ': ${_profileMemoryProfileId!}' : ''}',
                    style: const TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w700,
                      color: Colors.white,
                    ),
                  ),
                ),
            ],
          ),
          actions: [
            Container(
              margin: const EdgeInsets.only(right: 4),
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: _isConnected ? Colors.green : Colors.red,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                _isConnected ? 'Live' : 'Offline',
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            if (_profileMemoryLoaded)
              Container(
                margin: const EdgeInsets.only(right: 4),
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: NeuroColors.primary,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  'Memory $_profileMemoryLineCount',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            if (_profileMemoryLoaded && _profileMemoryCues.isNotEmpty)
              IconButton(
                onPressed: () {
                  final content = _profileMemoryCues.join('\n');
                  showDialog<void>(
                    context: context,
                    builder: (ctx) => AlertDialog(
                      title: const Text('Memory Cues in This Session'),
                      content: Text(content),
                      actions: [
                        TextButton(
                          onPressed: () => Navigator.pop(ctx),
                          child: const Text('OK'),
                        ),
                      ],
                    ),
                  );
                },
                icon: const Icon(Icons.psychology_alt_outlined),
                tooltip: 'View memory cues',
              ),
            if (widget.observerEnabled)
              IconButton(
                onPressed: _openObserverPanel,
                icon: const Icon(Icons.insights),
                tooltip: 'Observer Panel',
              ),
            IconButton(
              onPressed: _openDebugLog,
              icon: const Icon(Icons.bug_report),
              tooltip: 'Debug Log',
            ),
          ],
        ),
        body: Stack(
          children: [
            Column(
              children: [
                Expanded(
                  child: ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.fromLTRB(16, 16, 16, 120),
                    itemCount: _transcriptLog.length,
                    itemBuilder: (context, index) {
                      final entry = _transcriptLog[index];
                      final sender = entry['sender']!;
                      final text = entry['text']!;
                      final isGemini = sender == 'Gemini';
                      final isSystem = sender == 'System' || sender == 'Error';
                      final isLight =
                          Theme.of(context).brightness == Brightness.light;

                      return Align(
                        alignment: isSystem
                            ? Alignment.center
                            : (isGemini
                                ? Alignment.centerLeft
                                : Alignment.centerRight),
                        child: Container(
                          padding: const EdgeInsets.all(12),
                          margin: const EdgeInsets.symmetric(vertical: 4),
                          decoration: BoxDecoration(
                            color: isSystem
                                ? Colors.transparent
                                : (isGemini
                                    ? NeuroColors.surfaceVariant
                                    : NeuroColors.surface),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            isSystem ? text : '$sender: $text',
                            style: TextStyle(
                              color: isSystem
                                  ? Colors.grey
                                  : (isLight
                                      ? NeuroColors.textPrimary
                                      : Colors.white),
                              fontStyle: isSystem
                                  ? FontStyle.italic
                                  : FontStyle.normal,
                            ),
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ],
            ),
            if (widget.observerEnabled &&
                _cameraController != null &&
                _cameraController!.value.isInitialized)
              Positioned(
                top: 20 + _cameraPreviewOffset.dy,
                right: 16 - _cameraPreviewOffset.dx,
                child: GestureDetector(
                  onTap: () {
                    setState(() {
                      _cameraPreviewPaused = !_cameraPreviewPaused;
                    });
                  },
                  onPanUpdate: (details) {
                    setState(() {
                      _cameraPreviewOffset += details.delta;
                    });
                  },
                  child: Container(
                    width: 120,
                    height: 160,
                    decoration: BoxDecoration(
                      border: Border.all(color: NeuroColors.primary, width: 2),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(10),
                      child: Stack(
                        fit: StackFit.expand,
                        children: [
                          if (_cameraPreviewPaused)
                            Image.asset('assets/mascot02.png',
                                fit: BoxFit.cover)
                          else
                            CameraPreview(_cameraController!),
                          Positioned(
                            right: 6,
                            top: 6,
                            child: Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 6, vertical: 4),
                              decoration: BoxDecoration(
                                color: Colors.black.withValues(alpha: 0.45),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Text(
                                _cameraPreviewPaused ? 'Paused' : 'Live Cam',
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 10,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            if (widget.observerEnabled &&
                (_cameraController == null ||
                    !_cameraController!.value.isInitialized))
              Positioned(
                top: 20,
                right: 16,
                child: Container(
                  width: 120,
                  height: 182,
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: NeuroColors.surface,
                    border: Border.all(color: NeuroColors.primary, width: 2),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Column(
                    children: [
                      Expanded(
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(10),
                          child: Image.asset(
                            'assets/mascot02.png',
                            fit: BoxFit.cover,
                          ),
                        ),
                      ),
                      const SizedBox(height: 8),
                      SizedBox(
                        width: double.infinity,
                        child: OutlinedButton(
                          onPressed: _retryCameraInit,
                          child: const Text('Retry'),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            if (widget.observerEnabled && _cameraController != null)
              Positioned(
                top: 186,
                right: 16,
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                  decoration: BoxDecoration(
                    color: NeuroColors.surface.withValues(alpha: 0.92),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: NeuroColors.primary),
                  ),
                  child: const Text(
                    'Tap: pause/resume • Drag: move',
                    style: TextStyle(fontSize: 10),
                  ),
                ),
              ),
            Positioned(
              bottom: 24,
              left: 0,
              right: 0,
              child: Column(
                children: [
                  // ── Mic button: only active when connected & not thinking ──
                  GestureDetector(
                    onTap: (_isConnected &&
                            _state != AgentState.speaking &&
                            _state != AgentState.thinking)
                        ? _toggleMic
                        : (_isConnected &&
                                _state == AgentState.speaking &&
                                _isMicActive == false)
                            ? null
                            : (_isMicActive ? _toggleMic : null),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 200),
                      padding: const EdgeInsets.all(20),
                      decoration: BoxDecoration(
                        color: !_isConnected
                            ? Colors.grey.shade400
                            : (_state == AgentState.speaking
                                ? Colors.orange
                                : (_isMicActive
                                    ? Colors.redAccent
                                    : (_state == AgentState.thinking
                                        ? Colors.purple
                                        : NeuroColors.primary))),
                        shape: BoxShape.circle,
                        boxShadow: _isMicActive
                            ? [
                                BoxShadow(
                                  color: Colors.red.withValues(alpha: 0.5),
                                  blurRadius: 20,
                                  spreadRadius: 5,
                                ),
                              ]
                            : [],
                      ),
                      child: Icon(
                        !_isConnected
                            ? Icons.mic_off
                            : (_state == AgentState.speaking
                                ? Icons.volume_up
                                : (_isMicActive
                                    ? Icons.stop
                                    : (_state == AgentState.thinking
                                        ? Icons.hourglass_empty
                                        : Icons.mic))),
                        size: 40,
                        color: Colors.white,
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    !_isConnected
                        ? 'Not connected'
                        : (_state == AgentState.speaking
                            ? 'AI is speaking... wait to finish'
                            : (_isMicActive
                                ? 'Recording \u2022 Tap \u25A0 to send'
                                : (_state == AgentState.thinking
                                    ? 'AI is thinking... please wait'
                                    : 'Tap mic to record, then tap \u25A0 to send'))),
                    style: const TextStyle(
                      color: NeuroColors.textSecondary,
                      fontSize: 12,
                    ),
                  ),
                  const SizedBox(height: 12),

                  SizedBox(
                    width: 220,
                    height: 48,
                    child: ElevatedButton.icon(
                      onPressed: _state == AgentState.connecting
                          ? null
                          : (_isConnected
                              ? () async => _disconnect()
                              : _connect),
                      icon: Icon(
                        _isConnected
                            ? Icons.stop_circle_outlined
                            : (_state == AgentState.connecting
                                ? Icons.sync
                                : Icons.play_circle_outline),
                      ),
                      label: Text(
                        _isConnected
                            ? 'End Session'
                            : (_state == AgentState.connecting
                                ? 'Connecting...'
                                : 'Reconnect'),
                      ),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: _isConnected
                            ? Colors.red.shade400
                            : NeuroColors.primary,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(24),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
