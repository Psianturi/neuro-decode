package com.neurodecode.neurodecode_mobile

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import android.os.Build
import android.util.Log
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.LinkedBlockingDeque
import java.util.concurrent.TimeUnit

class MainActivity : FlutterActivity() {
	private val channelName = "neurodecode/live_audio"
	private val logTag = "NeuroDecodeAudio"
	private val maxQueueChunks = 48
	private val queueOfferTimeoutMs = 120L
	private val audioExecutor: ExecutorService = Executors.newSingleThreadExecutor()
	private val pcmQueue = LinkedBlockingDeque<ByteArray>(maxQueueChunks)
	private var audioTrack: AudioTrack? = null
	@Volatile private var playbackLoopRunning = false
	private var currentSampleRate: Int? = null
	private var currentChannelCount: Int? = null
	private var currentBufferBytes: Int? = null

	override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
		super.configureFlutterEngine(flutterEngine)

		MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channelName)
			.setMethodCallHandler { call, result ->
				when (call.method) {
					"initPlayer" -> {
						val sampleRate = call.argument<Int>("sampleRate") ?: 24000
						val channelCount = call.argument<Int>("channelCount") ?: 1
						val requestedBufferBytes = call.argument<Int>("bufferBytes") ?: 12288
						try {
							initPlayer(sampleRate, channelCount, requestedBufferBytes)
							result.success(null)
						} catch (e: Exception) {
							result.error("init_failed", e.message, null)
						}
					}

					"writePcm" -> {
						val bytes = call.argument<ByteArray>("bytes")
						if (bytes == null || bytes.isEmpty()) {
							result.success(null)
							return@setMethodCallHandler
						}
						while (!pcmQueue.offerLast(bytes, queueOfferTimeoutMs, TimeUnit.MILLISECONDS)) {
							val dropped = pcmQueue.pollFirst()
							Log.w(logTag, "Dropping stale PCM chunk bytes=${dropped?.size ?: 0}")
						}
						Log.d(logTag, "Queued PCM chunk bytes=${bytes.size} queueDepth=${pcmQueue.size}/$maxQueueChunks")
						result.success(null)
					}

					"stopPlayer" -> {
						stopPlayer()
						result.success(null)
					}

					"flushPlayer" -> {
						flushPlayer()
						result.success(null)
					}

					"releasePlayer" -> {
						releasePlayer()
						result.success(null)
					}

					else -> result.notImplemented()
				}
			}
	}

	private fun initPlayer(sampleRate: Int, channelCount: Int, requestedBufferBytes: Int) {
		val channelConfig = if (channelCount == 1) {
			AudioFormat.CHANNEL_OUT_MONO
		} else {
			AudioFormat.CHANNEL_OUT_STEREO
		}

		val minBufferBytes = AudioTrack.getMinBufferSize(
			sampleRate,
			channelConfig,
			AudioFormat.ENCODING_PCM_16BIT,
		)
		val bufferBytes = maxOf(minBufferBytes, requestedBufferBytes)

		val reusableTrack = audioTrack != null &&
			currentSampleRate == sampleRate &&
			currentChannelCount == channelCount &&
			currentBufferBytes == bufferBytes

		if (reusableTrack) {
			Log.d(
				logTag,
				"Reusing existing AudioTrack sampleRate=$sampleRate channelCount=$channelCount bufferBytes=$bufferBytes",
			)
			if (audioTrack?.playState != AudioTrack.PLAYSTATE_PLAYING) {
				audioTrack?.play()
				Log.d(logTag, "AudioTrack resumed")
			}
			ensurePlaybackLoop()
			return
		}

		releasePlayer()

		val trackBuilder = AudioTrack.Builder()
			.setAudioAttributes(
				AudioAttributes.Builder()
					.setUsage(AudioAttributes.USAGE_MEDIA)
					.setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
					.build(),
			)
			.setAudioFormat(
				AudioFormat.Builder()
					.setSampleRate(sampleRate)
					.setEncoding(AudioFormat.ENCODING_PCM_16BIT)
					.setChannelMask(channelConfig)
					.build(),
			)
			.setTransferMode(AudioTrack.MODE_STREAM)
			.setBufferSizeInBytes(bufferBytes)

		if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
			trackBuilder.setPerformanceMode(AudioTrack.PERFORMANCE_MODE_LOW_LATENCY)
		}

		audioTrack = trackBuilder.build()
		currentSampleRate = sampleRate
		currentChannelCount = channelCount
		currentBufferBytes = bufferBytes

		Log.d(
			logTag,
			"AudioTrack created sampleRate=$sampleRate channelCount=$channelCount minBufferBytes=$minBufferBytes bufferBytes=$bufferBytes",
		)
		audioTrack?.play()
		Log.d(logTag, "AudioTrack started")
		pcmQueue.clear()
		ensurePlaybackLoop()
	}

	private fun ensurePlaybackLoop() {
		if (playbackLoopRunning) {
			return
		}
		playbackLoopRunning = true
		Log.d(logTag, "Starting native playback loop")
		audioExecutor.execute {
			while (playbackLoopRunning && !Thread.currentThread().isInterrupted) {
				try {
					val chunk = pcmQueue.pollFirst(250, TimeUnit.MILLISECONDS) ?: continue
					val track = audioTrack ?: continue
					val written = track.write(chunk, 0, chunk.size, AudioTrack.WRITE_BLOCKING)
					Log.d(
						logTag,
						"AudioTrack write requested=${chunk.size} written=$written queueDepth=${pcmQueue.size} playState=${track.playState}",
					)
				} catch (_: InterruptedException) {
					Thread.currentThread().interrupt()
					break
				} catch (e: Exception) {
					Log.e(logTag, "Native PCM playback loop error", e)
				}
			}
			Log.d(logTag, "Native playback loop stopped")
		}
	}

	private fun stopPlayer() {
		Log.d(logTag, "stopPlayer() called; delegating to flushPlayer() to keep session-scoped track alive")
		flushPlayer()
	}

	private fun flushPlayer() {
		Log.d(logTag, "flushPlayer() called; clearing queueDepth=${pcmQueue.size}")
		pcmQueue.clear()
		try {
			audioTrack?.pause()
			audioTrack?.flush()
			audioTrack?.play()
			Log.d(logTag, "AudioTrack flushed and resumed")
		} catch (e: Exception) {
			Log.e(logTag, "flushPlayer() failed", e)
		}
	}

	private fun releasePlayer() {
		Log.d(logTag, "releasePlayer() called; queueDepth=${pcmQueue.size}")
		playbackLoopRunning = false
		pcmQueue.clear()
		try {
			audioTrack?.pause()
			audioTrack?.flush()
			audioTrack?.stop()
		} catch (_: Exception) {
		}
		try {
			audioTrack?.release()
		} catch (_: Exception) {
		}
		audioTrack = null
		currentSampleRate = null
		currentChannelCount = null
		currentBufferBytes = null
	}

	override fun onDestroy() {
		releasePlayer()
		audioExecutor.shutdownNow()
		super.onDestroy()
	}
}
