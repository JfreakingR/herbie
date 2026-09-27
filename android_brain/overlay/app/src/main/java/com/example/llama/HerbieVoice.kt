package com.prismml.herbiebrain

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import android.media.AudioManager
import android.media.MediaPlayer
import android.os.Bundle
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.nio.charset.StandardCharsets
import java.util.Locale
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * Herbie's voice through Android's own TTS engine, owned by the foreground
 * service. Termux:API's TTS hung on this phone (2026-09-27, Android 15) even
 * with Termux in the foreground; a service Android already keeps alive does not.
 *
 * The engine renders each utterance to a file and Herbie plays it himself as
 * media. Speaking directly came out as accessibility audio while TalkBack was on
 * (the phone has no screen, so TalkBack stays on) and never reached the
 * Bluetooth speaker; media playback follows the phone's media output.
 *
 * With internet and an ElevenLabs key (owner opted in 2026-09-27), the voice is
 * ElevenLabs v3, which acts out cues like [laughs] or [whispers]. Offline or on
 * any failure it falls back to Android TTS with the cues removed.
 */
class HerbieVoice(context: Context) {
    private val prefs = context.applicationContext
        .getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
    private val cacheDir: File = context.applicationContext.cacheDir
    private val audio = context.getSystemService(AudioManager::class.java)
    @Volatile private var hushed = false
    private val playLock = Any()
    @Volatile private var player: MediaPlayer? = null
    @Volatile private var playing: CountDownLatch? = null
    @Volatile private var streamTrack: AudioTrack? = null
    @Volatile private var streamConnection: HttpURLConnection? = null
    @Volatile private var stopRequested = false
    @Volatile private var ready = false
    private val pending = ConcurrentHashMap<String, CountDownLatch>()
    private val tts: TextToSpeech = TextToSpeech(context.applicationContext) { status ->
        ready = status == TextToSpeech.SUCCESS && configure()
        Log.i(TAG, "Voice ready=$ready (init status $status)")
    }

    val isReady: Boolean get() = ready

    private fun configure(): Boolean {
        val language = tts.setLanguage(Locale.US)
        if (language == TextToSpeech.LANG_MISSING_DATA ||
            language == TextToSpeech.LANG_NOT_SUPPORTED
        ) {
            return false
        }
        tts.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String) = Unit
            override fun onDone(utteranceId: String) = finish(utteranceId)
            override fun onStop(utteranceId: String, interrupted: Boolean) = finish(utteranceId)
            @Deprecated("Deprecated in Android")
            override fun onError(utteranceId: String) = finish(utteranceId)
            override fun onError(utteranceId: String, errorCode: Int) = finish(utteranceId)
        })
        return true
    }

    private fun finish(utteranceId: String) {
        pending.remove(utteranceId)?.countDown()
    }

    /**
     * Mutes the recognizer's start/stop beeps, which the owner does not want.
     * They play every time listening restarts. Speaking unmutes first.
     */
    fun hushEarcons() = setHushed(true)

    private fun setHushed(value: Boolean) {
        if (hushed == value) return
        val direction = if (value) AudioManager.ADJUST_MUTE else AudioManager.ADJUST_UNMUTE
        for (stream in EARCON_STREAMS) {
            // Muting some streams needs Do Not Disturb access; skip those.
            runCatching { audio.adjustStreamVolume(stream, direction, 0) }
        }
        hushed = value
    }

    /** Speaks and blocks until the utterance ends, is stopped, or times out. */
    fun speak(text: String, pitch: Float, rate: Float): Boolean {
        setHushed(false)
        synchronized(playLock) {
            stopRequested = false
            // Streaming first so he starts talking within about a second; a
            // stream that never started falls back to a full render.
            streamWithElevenLabs(text)?.let { return it }
            val cloudFile = renderWithElevenLabs(text)
            if (cloudFile != null) return play(cloudFile)
            if (!ready) return false
            val spoken = text.replace(VOICE_CUE, "").replace(Regex("""\s+"""), " ").trim()
            if (spoken.isEmpty()) return true
            val id = UUID.randomUUID().toString()
            val file = File(cacheDir, "utterance.wav")
            val rendered = CountDownLatch(1)
            pending[id] = rendered
            val queued = synchronized(tts) {
                tts.setPitch(pitch)
                tts.setSpeechRate(rate)
                tts.synthesizeToFile(spoken, Bundle(), file, id)
            }
            if (queued != TextToSpeech.SUCCESS) {
                pending.remove(id)
                return false
            }
            if (!rendered.await(SPEAK_TIMEOUT_SECONDS, TimeUnit.SECONDS) || file.length() == 0L) {
                return false
            }
            return play(file)
        }
    }

    private fun elevenLabsRequest(path: String, text: String, accept: String): HttpURLConnection? {
        val key = prefs.getString(ELEVENLABS_KEY, null)?.takeIf { it.length >= 20 } ?: return null
        val voiceId = prefs.getString(ELEVENLABS_VOICE, null)?.takeIf { it.isNotBlank() } ?: return null
        return runCatching {
            (URL("$ELEVENLABS_URL$voiceId$path").openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = 5_000
                readTimeout = 30_000
                doOutput = true
                setRequestProperty("xi-api-key", key)
                setRequestProperty("Content-Type", "application/json")
                setRequestProperty("Accept", accept)
                val body = JSONObject().put("text", text).put("model_id", ELEVENLABS_MODEL).toString()
                outputStream.use { it.write(body.toByteArray(StandardCharsets.UTF_8)) }
            }
        }.onFailure { Log.w(TAG, "ElevenLabs unreachable", it) }.getOrNull()
    }

    /**
     * Plays ElevenLabs PCM as it arrives. Null if the stream never started (so a
     * fallback may try); otherwise whether it played to the end.
     */
    private fun streamWithElevenLabs(text: String): Boolean? {
        val connection = elevenLabsRequest(
            "/stream?output_format=pcm_$STREAM_RATE", text, "audio/pcm",
        ) ?: return null
        var track: AudioTrack? = null
        try {
            if (connection.responseCode != 200) {
                Log.w(TAG, "ElevenLabs stream HTTP ${connection.responseCode} ${whyRefused(connection)}")
                return null
            }
            streamConnection = connection
            val minimum = AudioTrack.getMinBufferSize(
                STREAM_RATE, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT,
            )
            track = AudioTrack.Builder()
                .setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_MEDIA)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build(),
                )
                .setAudioFormat(
                    AudioFormat.Builder()
                        .setSampleRate(STREAM_RATE)
                        .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                        .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                        .build(),
                )
                .setBufferSizeInBytes(maxOf(minimum, STREAM_RATE)) // about 0.5 s of audio
                .setTransferMode(AudioTrack.MODE_STREAM)
                .build()
            streamTrack = track
            track.play()
            val buffer = ByteArray(8_192)
            var pending = 0 // an odd trailing byte carried into the next read
            var written = 0L
            connection.inputStream.use { input ->
                while (!stopRequested) {
                    val read = input.read(buffer, pending, buffer.size - pending)
                    if (read < 0) break
                    val total = pending + read
                    val even = total - total % 2
                    if (even > 0) written += track.write(buffer, 0, even)
                    pending = total - even
                    if (pending == 1) buffer[0] = buffer[even]
                }
            }
            if (stopRequested) return true
            // Let the buffered tail play out, then stop. (Stopping first resets the
            // playback head, so the wait would never see the end.)
            val frames = written / 2
            val deadline = System.currentTimeMillis() + 2_000 + frames * 1_000 / STREAM_RATE
            while (track.playbackHeadPosition < frames &&
                System.currentTimeMillis() < deadline && !stopRequested
            ) {
                Thread.sleep(20)
            }
            track.stop()
            return true
        } catch (failure: Exception) {
            Log.w(TAG, "ElevenLabs stream failed", failure)
            return if (track == null) null else false
        } finally {
            streamTrack = null
            streamConnection = null
            runCatching { track?.release() }
            connection.disconnect()
        }
    }

    /**
     * ElevenLabs' own reason for a refusal, e.g. quota_exceeded or
     * invalid_api_key - both come back as HTTP 401. Never includes the key.
     */
    private fun whyRefused(connection: HttpURLConnection): String = runCatching {
        val body = connection.errorStream?.use { String(it.readBytes(), StandardCharsets.UTF_8) }
            ?: return@runCatching ""
        val detail = JSONObject(body).opt("detail")
        if (detail is JSONObject) detail.optString("status").ifEmpty { detail.optString("message") }
        else detail?.toString().orEmpty()
    }.getOrDefault("").take(200)

    /** The utterance as ElevenLabs audio, or null to use the on-phone voice. */
    private fun renderWithElevenLabs(text: String): File? {
        val connection = elevenLabsRequest(
            "?output_format=mp3_44100_128", text, "audio/mpeg",
        ) ?: return null
        return try {
            if (connection.responseCode != 200) {
                Log.w(TAG, "ElevenLabs HTTP ${connection.responseCode} ${whyRefused(connection)}; using the phone voice")
                return null
            }
            val file = File(cacheDir, "utterance.mp3")
            connection.inputStream.use { input -> file.outputStream().use { input.copyTo(it) } }
            file.takeIf { it.length() > 0 }
        } catch (failure: Exception) {
            Log.w(TAG, "ElevenLabs unreachable; using the phone voice", failure)
            null
        } finally {
            connection.disconnect()
        }
    }

    private fun play(file: File): Boolean {
        val finished = CountDownLatch(1)
        val media = MediaPlayer()
        try {
            media.setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build(),
            )
            media.setDataSource(file.absolutePath)
            media.setOnCompletionListener { finished.countDown() }
            media.setOnErrorListener { _, _, _ -> finished.countDown(); true }
            media.prepare()
            player = media
            playing = finished
            media.start()
            return finished.await(SPEAK_TIMEOUT_SECONDS, TimeUnit.SECONDS)
        } catch (failure: Exception) {
            Log.e(TAG, "Playback failed", failure)
            return false
        } finally {
            player = null
            playing = null
            media.release()
        }
    }

    fun stop(): Boolean {
        stopRequested = true
        val track = streamTrack
        runCatching { track?.pause(); track?.flush() }
        runCatching { streamConnection?.disconnect() }
        val media = player
        val wasSpeaking = media != null || track != null
        if (ready) tts.stop()
        pending.keys.toList().forEach { finish(it) }
        runCatching { media?.stop() }
        playing?.countDown()
        return wasSpeaking
    }

    fun shutdown() {
        stop()
        setHushed(false)
        tts.shutdown()
        ready = false
    }

    companion object {
        private const val TAG = "HerbieVoice"
        private const val SPEAK_TIMEOUT_SECONDS = 120L
        private const val PREFERENCES = "herbie_private_bridge"
        private const val ELEVENLABS_KEY = "elevenlabs_key"
        private const val ELEVENLABS_VOICE = "elevenlabs_voice"
        private const val ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech/"
        private const val ELEVENLABS_MODEL = "eleven_v3"
        private const val STREAM_RATE = 24_000
        // Cues such as [laughs] that only the ElevenLabs voice can act out.
        private val VOICE_CUE = Regex("""\[[^\]]{1,40}\]""")
        private val EARCON_STREAMS = intArrayOf(
            AudioManager.STREAM_MUSIC,
            AudioManager.STREAM_SYSTEM,
            AudioManager.STREAM_NOTIFICATION,
        )
    }
}
