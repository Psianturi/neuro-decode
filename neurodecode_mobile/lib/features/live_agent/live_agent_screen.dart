import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_sound/flutter_sound.dart';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
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
  });

  final List<CameraDescription> cameras;
  final bool observerEnabled;

  @override
  State<LiveAgentScreen> createState() => _LiveAgentScreenState();
}

class _LiveAgentScreenState extends State<LiveAgentScreen> {
  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _wsSub;
  AgentState _state = AgentState.idle;

  final AudioRecorder _recorder = AudioRecorder();
  StreamSubscription<Uint8List>? _micStreamSub;
  bool _isMicActive = false;
  final FlutterSoundPlayer _soundPlayer = FlutterSoundPlayer();
  bool _isPlayerReady = false;
  bool _isPlayerStreamOpen = false;
  bool _geminiTurnComplete = true;
  Future<void>? _feedChain;
  static const int _playerBufferSize = 4096;
  CameraController? _cameraController;
  Timer? _visionTimer;
  bool _isCapturingFrame = false;
  bool _isCleaningUp = false;

  bool _seenTranscriptOutInCurrentTurn = false;
  DateTime? _lastGeminiChunkAt;
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

  bool get _isConnected =>
      _channel != null && _wsSub != null && _state != AgentState.error;

  void _setStateLabel(AgentState next) {
    if (!mounted) return;
    setState(() {
      _state = next;
    });
  }

  void _connect() {
    if (_isConnected) return;
    _setStateLabel(AgentState.connecting);
    _logDebug('ws_event', 'connecting ${AppConfig.wsEndpoint}');
    try {
      _channel = WebSocketChannel.connect(Uri.parse(AppConfig.wsEndpoint));
      _wsSub = _channel!.stream.listen(
        _onMessageReceived,
        onDone: () => _handleSocketClosed(manual: false),
        onError: (error) {
          _setStateLabel(AgentState.error);
          _addLog('Error', 'Connection error: $error');
          _logDebug('ws_event', 'error: $error');
          _handleSocketClosed(manual: false);
        },
      );

      if (!mounted) return;
      _setStateLabel(AgentState.idle);
      _addLog('System', 'Establishing secure connection...');
      _logDebug('ws_event', 'connected');
    } catch (e) {
      _setStateLabel(AgentState.error);
      _addLog('System', 'Failed to connect: $e');
      _logDebug('ws_event', 'failed: $e');
    }
  }

  void _disconnect() {
    _stopVisionLoop();
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
    final data = jsonDecode(message as String);
    final type = data['type'];
    _logDebug('ws_event', 'message type=$type');

    if (type == 'transcript_in') {
      final text = (data['text'] ?? '').toString();
      if (text.isNotEmpty) {
        _addLog('You', text);
      }
      return;
    }

    if (type == 'transcript_out') {
      _setStateLabel(AgentState.speaking);
      _seenTranscriptOutInCurrentTurn = true;
      final text = (data['text'] ?? '').toString();
      if (text.isNotEmpty) {
        _appendGeminiChunk(text);
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
      final b64 = (data['data_b64'] ?? '').toString();
      if (b64.isNotEmpty) {
        _feedAudio(Uint8List.fromList(base64Decode(b64)));
      }
      return;
    }

    if (type == 'model_audio_end') {
      _geminiTurnComplete = true;
      _seenTranscriptOutInCurrentTurn = false;
      _lastGeminiChunkAt = null;
      // Delay state change so OS audio buffer can drain
      Future.delayed(const Duration(milliseconds: 600), () {
        if (mounted && _geminiTurnComplete) {
          _closePlayerStream();
          _setStateLabel(AgentState.idle);
        }
      });
      return;
    }

    if (type == 'interrupted') {
      _stopPlayerStreamNow();
      _geminiTurnComplete = true;
      _addLog('System', 'Gemini response interrupted.');
      _logDebug('player_event', 'interrupted, stream stopped');
      _setStateLabel(AgentState.idle);
      return;
    }

    if (type == 'error') {
      _setStateLabel(AgentState.error);
      final text = (data['message'] ?? 'Unknown backend error').toString();
      _addLog('Error', text);
    }

    if (type == 'observer_note') {
      final text = (data['text'] ?? '').toString();
      if (text.isNotEmpty) {
        _addObserverEvent(
          text: text,
          confidence: ObserverConfidence.medium,
        );
      }
    }
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
    if (_isMicActive) {
      await _stopMicStream();
    } else {
      //stop Gemini audio if it's speaking when user starts talking
      if (_state == AgentState.speaking) {
        _stopPlayerStreamNow();
        _geminiTurnComplete = true;
        _logDebug('barge_in', 'user interrupted Gemini, audio stopped');
      }
      await _startMicStream();
    }
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
    if (!_isConnected || _channel == null) return;
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
      setState(() { _isMicActive = false; });
    }
  }

  Future<void> _stopMicStream() async {
    if (!_isMicActive) return;

    await _micStreamSub?.cancel();
    _micStreamSub = null;
    await _recorder.stop();
    _logDebug('mic_event', 'toggle OFF — streaming stopped');

    if (_isConnected && _channel != null) {
      _channel!.sink.add(
        jsonEncode(
          {
            'type': 'text',
            'text': '',
            'end_of_turn': true,
          },
        ),
      );
      _logDebug('turn_event', 'commit sent end_of_turn=true');
    }

    if (mounted) {
      setState(() {
        _isMicActive = false;
      });
    }
    _setStateLabel(AgentState.thinking);
  }

  // ── PCM streaming audio playback (pipe-to-speaker) ──

  void _feedAudio(Uint8List pcm) {
    // Chain feed operations to ensure sequential execution.
    _feedChain = (_feedChain ?? Future.value())
        .then((_) => _doFeedAudio(pcm))
        .catchError((e) => _logDebug('player_event', 'feed error: $e'));
  }

  Future<void> _doFeedAudio(Uint8List pcm) async {
    if (!_isPlayerReady) return;
    if (!_isPlayerStreamOpen) {
      await _soundPlayer.startPlayerFromStream(
        codec: Codec.pcm16,
        interleaved: true,
        sampleRate: 24000,
        numChannels: 1,
        bufferSize: _playerBufferSize,
      );
      _isPlayerStreamOpen = true;
      _logDebug('player_event', 'PCM stream opened at 24kHz');
    }
    await _soundPlayer.feedFromStream(pcm);
  }

  void _closePlayerStream() {
    if (_isPlayerStreamOpen) {
      _soundPlayer.stopPlayer();
      _isPlayerStreamOpen = false;
      _feedChain = null;
      _logDebug('player_event', 'PCM stream closed');
    }
  }

  void _stopPlayerStreamNow() {
    if (_isPlayerStreamOpen) {
      _soundPlayer.stopPlayer();
      _isPlayerStreamOpen = false;
      _feedChain = null;
    }
  }

  void _logDebug(String tag, String msg) {
    final ts = DateFormat('HH:mm:ss').format(DateTime.now());
    if (!mounted) return;
    setState(() {
      _debugLog.add('[$ts] $tag: $msg');
      if (_debugLog.length > 200) {
        _debugLog.removeRange(0, _debugLog.length - 200);
      }
    });
  }

  void _appendGeminiChunk(String chunk) {
    final normalized = chunk.trim();
    if (normalized.isEmpty || !mounted) return;

    final now = DateTime.now();
    final shouldMerge = _transcriptLog.isNotEmpty &&
        _transcriptLog.last['sender'] == 'Gemini' &&
        _lastGeminiChunkAt != null &&
        now.difference(_lastGeminiChunkAt!) < const Duration(milliseconds: 1200);

    setState(() {
      if (shouldMerge) {
        final previous = _transcriptLog.last['text'] ?? '';
        final needsSpace = previous.isNotEmpty &&
            !previous.endsWith(' ') &&
            !RegExp(r'^[,.;:!?)]').hasMatch(normalized);
        final merged = needsSpace ? '$previous $normalized' : '$previous$normalized';
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

  void _addLog(String sender, String message) {
    if (!mounted || message.isEmpty) return;
    setState(() {
      _transcriptLog.add({'sender': sender, 'text': message});
    });
    _scrollToBottom();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
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

    if (mounted) {
      _setStateLabel(AgentState.idle);
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
    _soundPlayer.closePlayer();
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Live Session • $_stateLabel'),
        actions: [
          if (widget.observerEnabled)
            IconButton(
              onPressed: _openObserverPanel,
              icon: const Icon(Icons.insights),
              tooltip: 'Observer Panel',
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
                    final isLight = Theme.of(context).brightness == Brightness.light;

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
                                : (isLight ? NeuroColors.textPrimary : Colors.white),
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
              top: 20,
              right: 16,
              child: Container(
                width: 120,
                height: 160,
                decoration: BoxDecoration(
                  border: Border.all(color: NeuroColors.primary, width: 2),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(10),
                  child: CameraPreview(_cameraController!),
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
                height: 160,
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: NeuroColors.surface,
                  border: Border.all(color: NeuroColors.primary, width: 2),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(10),
                  child: Image.asset(
                    'assets/mascot02.png',
                    fit: BoxFit.cover,
                  ),
                ),
              ),
            ),
          Positioned(
            bottom: 24,
            left: 0,
            right: 0,
            child: Column(
              children: [
                // ── Mic button: only active when connected ──
                GestureDetector(
                  onTap: (_isConnected && _state != AgentState.speaking)
                      ? _toggleMic
                      : null,
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
                                  : NeuroColors.primary)),
                      shape: BoxShape.circle,
                      boxShadow: _isMicActive
                          ? [
                              const BoxShadow(
                                color: Colors.red,
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
                          ? 'AI is speaking...'
                          : (_isMicActive
                              ? 'Recording... tap again to send'
                              : 'Tap once to record, tap again to send')),
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
                    onPressed:
                        _state == AgentState.connecting
                            ? null
                            : (_isConnected ? _disconnect : _connect),
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
                      backgroundColor:
                          _isConnected ? Colors.red.shade400 : NeuroColors.primary,
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
    );
  }
}
