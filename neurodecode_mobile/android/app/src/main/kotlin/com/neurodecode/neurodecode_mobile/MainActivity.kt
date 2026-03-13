package com.neurodecode.neurodecode_mobile

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioTrack
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

class MainActivity : FlutterActivity() {
	private val channelName = "neurodecode/live_audio"
	private val audioExecutor: ExecutorService = Executors.newSingleThreadExecutor()
	private var audioTrack: AudioTrack? = null

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
						audioExecutor.execute {
							try {
								audioTrack?.write(bytes, 0, bytes.size, AudioTrack.WRITE_BLOCKING)
							} catch (_: Exception) {
							}
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
		val bufferBytes = maxOf(minBufferBytes * 2, requestedBufferBytes)

		audioTrack = AudioTrack.Builder()
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
			.build()

		audioTrack?.play()
	}

	private fun stopPlayer() {
		try {
			audioTrack?.pause()
			audioTrack?.flush()
			audioTrack?.stop()
		} catch (_: Exception) {
		}
	}

	private fun releasePlayer() {
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
