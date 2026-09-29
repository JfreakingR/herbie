package com.prismml.herbiebrain

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Color
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.provider.Settings
import android.util.Log
import android.view.Display
import android.view.WindowManager
import android.webkit.WebView
import android.webkit.WebViewClient
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.nio.charset.StandardCharsets

/**
 * Herbie's face on the 7-inch HDMI screen plugged into the Galaxy (USB-C to
 * HDMI). It is his existing BMO face, pi_bridge/face/index.html, which the
 * build copies into the app's assets; nothing here draws a face of its own.
 *
 * The phone's own screen is broken, so the face goes wherever Android reports
 * a presentation display, and comes and goes with the cable. It is owned by
 * the foreground service, so no activity needs to be in front: the page is an
 * "Appear on top" window on that display (the permission the boot receiver
 * already relies on). With DeX auto-start off, Android mirrors the phone onto
 * HDMI until something draws there; this window replaces the mirror.
 *
 * The page is driven through its own window.BotFace API. Mood comes from the
 * phone brain's /v1/expression; talking, thinking and listening come straight
 * from the voice and ears, so the mouth moves while the audio actually plays.
 * The page never speaks: its speech synthesis is left unused and Herbie's
 * voice stays HerbieVoice's.
 */
class HerbieFace(
    context: Context,
    private val voice: () -> HerbieVoice?,
    private val ears: () -> HerbieEars?,
    private val brainToken: () -> String?,
) {
    private val app = context.applicationContext
    private val main = Handler(Looper.getMainLooper())
    private val displays = app.getSystemService(DisplayManager::class.java)
    private var shown: Shown? = null
    private var pageReady = false
    private var lastEmotion = ""
    private var lastMode = ""
    @Volatile private var running = false
    @Volatile private var expression = "calm"

    private class Shown(val displayId: Int, val windows: WindowManager, val page: WebView)

    private val listener = object : DisplayManager.DisplayListener {
        override fun onDisplayAdded(displayId: Int) = attach()
        override fun onDisplayRemoved(displayId: Int) {
            if (shown?.displayId == displayId) detach()
        }
        override fun onDisplayChanged(displayId: Int) = attach()
    }

    private val drive = object : Runnable {
        override fun run() {
            if (!running) return
            push()
            main.postDelayed(this, DRIVE_MS)
        }
    }

    fun start() = main.post {
        if (running) return@post
        running = true
        displays.registerDisplayListener(listener, main)
        attach()
        main.post(drive)
        Thread({ followBrain() }, "herbie-face-mood").apply {
            isDaemon = true
            start()
        }
    }

    fun stop() = main.post {
        running = false
        main.removeCallbacks(drive)
        displays.unregisterDisplayListener(listener)
        detach()
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun attach() {
        if (!running || shown != null) return
        val display = displays.getDisplays(DisplayManager.DISPLAY_CATEGORY_PRESENTATION)
            .firstOrNull { it.displayId != Display.DEFAULT_DISPLAY && it.state != Display.STATE_OFF }
            ?: return
        if (!Settings.canDrawOverlays(app)) {
            Log.w(TAG, "Screen ${display.name} found, but Appear on top is not granted; no face")
            return
        }
        try {
            val windowContext = app.createDisplayContext(display)
                .createWindowContext(WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY, null)
            val windows = windowContext.getSystemService(WindowManager::class.java)
            val page = WebView(windowContext).apply {
                setBackgroundColor(LCD)
                settings.javaScriptEnabled = true
                settings.mediaPlaybackRequiresUserGesture = true
                webViewClient = object : WebViewClient() {
                    override fun onPageFinished(view: WebView, url: String) {
                        // Same as ?kiosk=1 on Melba: hides the dock. Asset URLs
                        // cannot carry a query string, so it is set here.
                        view.evaluateJavascript("document.body.classList.add('kiosk')", null)
                        pageReady = true
                        lastEmotion = ""
                        lastMode = ""
                        push()
                    }
                }
            }
            val params = WindowManager.LayoutParams(
                WindowManager.LayoutParams.MATCH_PARENT,
                WindowManager.LayoutParams.MATCH_PARENT,
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                    WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or
                    WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON or
                    WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
                    WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
                PixelFormat.OPAQUE,
            ).apply { title = "Herbie face" }
            windows.addView(page, params)
            pageReady = false
            page.loadUrl(FACE_URL)
            shown = Shown(display.displayId, windows, page)
            Log.i(TAG, "Face on ${display.name} (${display.mode.physicalWidth}x${display.mode.physicalHeight})")
        } catch (refused: Exception) {
            Log.w(TAG, "Could not put the face on ${display.name}", refused)
        }
    }

    private fun detach() {
        val current = shown ?: return
        shown = null
        pageReady = false
        runCatching { current.windows.removeViewImmediate(current.page) }
        current.page.destroy()
        Log.i(TAG, "Face screen gone")
    }

    /**
     * Tells the page what Herbie is doing, only when it changes, so the page's
     * own blinking and idle motion are not reset every tick. Same order of
     * precedence as the page's followHerbie(): talking, then asleep, then
     * listening, then plain mood.
     */
    private fun push() {
        val page = shown?.page ?: return
        if (!pageReady) return
        val emotion = FACE_FROM_HERBIE[expression] ?: "neutral"
        val earState = ears()?.state
        val mode = when {
            voice()?.isSpeaking == true -> "talk"
            ears()?.thinking == true -> "think"
            expression == "sleepy" -> "sleep"
            earState == HerbieEars.State.AWAKE -> "listen"
            else -> "idle"
        }
        val script = StringBuilder()
        val modeChanged = mode != lastMode
        if (modeChanged) {
            if (lastMode == "talk") script.append("BotFace.stopTalking();")
            script.append(
                when (mode) {
                    "talk" -> "BotFace.startTalking();"
                    "think" -> "BotFace.think();"
                    "sleep" -> "BotFace.sleep();"
                    "listen" -> "BotFace.listen();"
                    else -> "BotFace.idle();"
                },
            )
        }
        // listen/think/sleep choose their own look; the page's idle() swaps a
        // listening or thinking look for happy, so the mood goes back on after.
        val moodShows = mode == "idle" || mode == "talk"
        if (moodShows && (modeChanged || emotion != lastEmotion)) {
            script.append("BotFace.setEmotion('$emotion');")
        }
        if (script.isEmpty()) return
        lastEmotion = emotion
        lastMode = mode
        page.evaluateJavascript("if (window.BotFace) { $script }", null)
    }

    /** Polls the phone brain for mood. A quiet failure keeps the last face. */
    private fun followBrain() {
        while (running) {
            val token = brainToken()
            if (token != null && shown != null) {
                runCatching { expression = fetchExpression(token) }
                    .onFailure { Log.d(TAG, "Brain expression unavailable: ${it.message}") }
            }
            SystemClock.sleep(POLL_MS)
        }
    }

    private fun fetchExpression(token: String): String {
        val connection = URL(BRAIN_EXPRESSION_URL).openConnection() as HttpURLConnection
        try {
            connection.connectTimeout = 2_000
            connection.readTimeout = 3_000
            connection.setRequestProperty("Authorization", "Bearer $token")
            check(connection.responseCode == 200) { "brain_http_${connection.responseCode}" }
            val body = connection.inputStream.use { String(it.readBytes(), StandardCharsets.UTF_8) }
            return JSONObject(body).optString("expression", "calm")
        } finally {
            connection.disconnect()
        }
    }

    companion object {
        private const val TAG = "HerbieFace"
        private const val FACE_URL = "file:///android_asset/face/index.html"
        private const val BRAIN_EXPRESSION_URL = "http://127.0.0.1:8765/v1/expression"
        private const val POLL_MS = 1_500L
        private const val DRIVE_MS = 150L
        private val LCD = Color.rgb(0x88, 0xC4, 0xAE)

        // The page's own table (FACE_FROM_HERBIE in index.html).
        private val FACE_FROM_HERBIE = mapOf(
            "calm" to "neutral",
            "curious" to "listen",
            "happy" to "happy",
            "playful" to "smirk",
            "thinking" to "thinking",
            "surprised" to "surprised",
            "concerned" to "sorry",
            "sleepy" to "sleepy",
        )
    }
}
