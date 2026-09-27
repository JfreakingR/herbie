package com.prismml.herbiebrain

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.nio.charset.StandardCharsets
import java.util.concurrent.Executors

/**
 * Herbie's ears: Android's recognizer, on-device when the phone has one, because
 * he has to hear with no network. Otherwise the standard recognizer, which may
 * use the cloud when online (the owner allowed that on 2026-09-27) and prefers
 * the offline language pack.
 *
 * Asleep, he only listens for his name. Awake, everything heard goes to his
 * phone brain (/v1/chat on 127.0.0.1:8765) and the reply is spoken. A sleep
 * phrase puts him back to sleep. He never listens while he is talking, so he
 * does not hear himself.
 *
 * He tells the brain's expression state when he is listening (awake) and
 * speaking, so a face on a screen (desk/herbie_desk.py) can follow along.
 */
class HerbieEars(
    private val context: Context,
    private val voice: HerbieVoice,
    private val brainToken: String,
) {
    enum class State { OFF, ASLEEP, AWAKE }

    @Volatile var state = State.OFF
        private set
    private val main = Handler(Looper.getMainLooper())
    private val worker = Executors.newSingleThreadExecutor()
    private var recognizer: SpeechRecognizer? = null
    @Volatile private var running = false
    @Volatile var mode = "none"
        private set

    fun start() = main.post {
        if (running) return@post
        val onDevice = SpeechRecognizer.isOnDeviceRecognitionAvailable(context)
        if (!onDevice && !SpeechRecognizer.isRecognitionAvailable(context)) {
            Log.w(TAG, "No speech recognizer on this phone; ears stay off")
            return@post
        }
        recognizer = (
            if (onDevice) SpeechRecognizer.createOnDeviceSpeechRecognizer(context)
            else SpeechRecognizer.createSpeechRecognizer(context)
            ).apply { setRecognitionListener(listener) }
        mode = if (onDevice) "on-device" else "standard"
        Log.i(TAG, "Ears using the $mode recognizer")
        running = true
        state = State.ASLEEP
        listen()
    }

    fun stop() = main.post {
        running = false
        state = State.OFF
        worker.execute { showActivity(listening = false, speaking = false) }
        recognizer?.destroy()
        recognizer = null
    }

    private fun listen() {
        if (!running) return
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-US")
            .putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true)
        voice.hushEarcons()
        runCatching { recognizer?.startListening(intent) }
            .onFailure { Log.e(TAG, "startListening failed", it); listenSoon(RETRY_MS) }
    }

    private fun listenSoon(delayMs: Long) {
        if (running) main.postDelayed({ listen() }, delayMs)
    }

    private val listener = object : RecognitionListener {
        override fun onResults(results: Bundle) {
            val heard = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                ?.firstOrNull()?.trim().orEmpty()
            if (heard.isEmpty()) return listenSoon(0)
            // Stop the loop until this utterance is fully handled and answered.
            worker.execute {
                handle(heard)
                listenSoon(AFTER_SPEAKING_MS)
            }
        }

        override fun onError(error: Int) {
            // No match and silence timeouts are normal between utterances.
            val delay = when (error) {
                SpeechRecognizer.ERROR_NO_MATCH, SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> 0L
                SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> RETRY_MS
                else -> { Log.w(TAG, "Recognizer error $error"); RETRY_MS }
            }
            listenSoon(delay)
        }

        override fun onReadyForSpeech(params: Bundle?) = Unit
        override fun onBeginningOfSpeech() = Unit
        override fun onRmsChanged(rmsdB: Float) = Unit
        override fun onBufferReceived(buffer: ByteArray?) = Unit
        override fun onEndOfSpeech() = Unit
        override fun onPartialResults(partialResults: Bundle?) = Unit
        override fun onEvent(eventType: Int, params: Bundle?) = Unit
    }

    private fun handle(heard: String) {
        Log.i(TAG, "Heard ($state): $heard")
        val lower = heard.lowercase()
        if (state == State.ASLEEP) {
            val at = lower.indexOf(WAKE_WORD)
            if (at < 0) return
            state = State.AWAKE
            Log.i(TAG, "Woke up")
            showActivity(listening = true, speaking = false)
            val rest = heard.substring(at + WAKE_WORD.length).trim(' ', ',', '.', '!', '?')
            if (rest.isEmpty()) say("I'm listening.") else converse(rest)
            return
        }
        if (SLEEP_PHRASES.any { it in lower }) {
            state = State.ASLEEP
            Log.i(TAG, "Went to sleep")
            say("Okay. Say my name when you need me.")
            return
        }
        converse(heard)
    }

    private fun converse(message: String) {
        // Not listening while he thinks, so the face drops its listening look.
        showActivity(listening = false, speaking = false)
        val reply = runCatching { askBrain(message) }
            .onFailure { Log.e(TAG, "Brain unavailable", it) }
            .getOrNull()
        say(reply ?: "Sorry, my brain didn't answer.")
    }

    private fun say(text: String) {
        showActivity(listening = false, speaking = true)
        try {
            voice.speak(text.take(MAX_SPEECH_CHARS), 1.0f, 1.0f)
        } finally {
            showActivity(listening = state == State.AWAKE, speaking = false)
        }
    }

    /** Best effort: a face that misses one update is better than a mute Herbie. */
    private fun showActivity(listening: Boolean, speaking: Boolean) {
        runCatching {
            val connection = URL(BRAIN_EXPRESSION_URL).openConnection() as HttpURLConnection
            try {
                connection.requestMethod = "POST"
                connection.connectTimeout = 1_000
                connection.readTimeout = 2_000
                connection.doOutput = true
                connection.setRequestProperty("Authorization", "Bearer $brainToken")
                connection.setRequestProperty("Content-Type", "application/json")
                // Privacy mode refuses listening=true; that refusal is correct.
                val body = JSONObject().put("listening", listening).put("speaking", speaking).toString()
                connection.outputStream.use { it.write(body.toByteArray(StandardCharsets.UTF_8)) }
                connection.responseCode
            } finally {
                connection.disconnect()
            }
        }.onFailure { Log.w(TAG, "Could not update the face: $it") }
    }

    private fun askBrain(message: String): String {
        val connection = URL(BRAIN_CHAT_URL).openConnection() as HttpURLConnection
        try {
            connection.requestMethod = "POST"
            connection.connectTimeout = 5_000
            connection.readTimeout = 300_000
            connection.doOutput = true
            connection.setRequestProperty("Authorization", "Bearer $brainToken")
            connection.setRequestProperty("Content-Type", "application/json")
            val body = JSONObject().put("message", message).put("max_tokens", 128).toString()
            connection.outputStream.use { it.write(body.toByteArray(StandardCharsets.UTF_8)) }
            check(connection.responseCode == 200) { "brain_http_${connection.responseCode}" }
            val response = connection.inputStream.use { String(it.readBytes(), StandardCharsets.UTF_8) }
            return JSONObject(response).getString("text").trim()
        } finally {
            connection.disconnect()
        }
    }

    companion object {
        private const val TAG = "HerbieEars"
        private const val BRAIN_CHAT_URL = "http://127.0.0.1:8765/v1/chat"
        private const val BRAIN_EXPRESSION_URL = "http://127.0.0.1:8765/v1/expression"
        private const val WAKE_WORD = "herbie"
        private val SLEEP_PHRASES = listOf("go to sleep", "stop listening")
        private const val RETRY_MS = 1_000L
        // Lets the tail of his own voice die away before he listens again.
        private const val AFTER_SPEAKING_MS = 700L
        private const val MAX_SPEECH_CHARS = 1_000
    }
}
