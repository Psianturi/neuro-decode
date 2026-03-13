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
	private val audioExecutor: ExecutorService = Executors.newSingleThreadExecutor()
	private val pcmQueue = LinkedBlockingDeque<ByteArray>(6)
	private var audioTrack: AudioTrack? = null
	@Volatile private var playbackLoopRunning = false

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
						while (!pcmQueue.offerLast(bytes)) {
							val dropped = pcmQueue.pollFirst()
							Log.w(logTag, "Dropping stale PCM chunk bytes=${dropped?.size ?: 0}")
						}
						result.success(null)
					}

					"stopPlayer" -> {
						stopPlayer()
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
		releasePlayer()

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

		audioTrack?.play()
		pcmQueue.clear()
		playbackLoopRunning = true
		audioExecutor.execute {
			while (playbackLoopRunning && !Thread.currentThread().isInterrupted) {
				try {
					val chunk = pcmQueue.pollFirst(250, TimeUnit.MILLISECONDS) ?: continue
					audioTrack?.write(chunk, 0, chunk.size, AudioTrack.WRITE_BLOCKING)
				} catch (_: InterruptedException) {
					Thread.currentThread().interrupt()
					break
				} catch (e: Exception) {
					Log.e(logTag, "Native PCM playback loop error", e)
				}
			}
		}
	}

	private fun stopPlayer() {
		playbackLoopRunning = false
		pcmQueue.clear()
		try {
			audioTrack?.pause()
			audioTrack?.flush()
			audioTrack?.stop()
		} catch (_: Exception) {
		}
	}

	private fun releasePlayer() {
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
	}

	override fun onDestroy() {
		releasePlayer()
		audioExecutor.shutdownNow()
		super.onDestroy()
	}
}
