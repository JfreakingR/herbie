package com.prismml.herbiebrain

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.content.Intent
import android.os.IBinder
import android.util.Log
import com.arm.aichat.AiChat
import com.arm.aichat.InferenceEngine
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import java.io.File

/** Keeps Herbie's local model and authenticated loopback bridge alive. */
class HerbieModelService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private val inferenceMutex = Mutex()
    private var engine: InferenceEngine? = null
    private var bridge: LocalBridgeServer? = null
    private var voice: HerbieVoice? = null
    private var ears: HerbieEars? = null
    @Volatile private var loading = false

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        val canHear = startInForeground()
        voice = HerbieVoice(this)
        if (canHear) startEars()
        startModelIfNeeded()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startModelIfNeeded()
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    /**
     * Android 14+ only lets a service use the microphone if it says so when it
     * goes foreground, and refuses that type when started from the background
     * (e.g. at boot). Returns whether the microphone type was granted.
     */
    private fun startInForeground(): Boolean {
        val starting = notification("Starting local conversation model…")
        val micGranted = checkSelfPermission(android.Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED
        if (micGranted) {
            try {
                startForeground(
                    NOTIFICATION_ID,
                    starting,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE or
                        ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE,
                )
                return true
            } catch (refused: Exception) {
                Log.w(TAG, "Microphone foreground refused; running without ears", refused)
            }
        }
        startForeground(NOTIFICATION_ID, starting, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        return false
    }

    private fun startEars() {
        val brainToken = getSharedPreferences(PREFERENCES, MODE_PRIVATE)
            .getString(BRAIN_TOKEN_KEY, null)
            ?.trim()
            ?.takeIf { it.length >= 16 }
        if (brainToken == null) {
            Log.w(TAG, "Brain token missing; ears stay off")
            return
        }
        ears = HerbieEars(this, checkNotNull(voice), brainToken).also { it.start() }
    }

    private fun startModelIfNeeded() {
        if (loading || bridge != null) return
        loading = true
        scope.launch {
            try {
                val token = getSharedPreferences(PREFERENCES, MODE_PRIVATE)
                    .getString(TOKEN_KEY, null)
                    ?.trim()
                    ?.takeIf { it.length >= 16 }
                    ?: error("bridge_token_missing")
                val model = discoverModel() ?: error("local_model_missing")
                val localEngine = AiChat.getInferenceEngine(applicationContext)
                val initialState = localEngine.state.first {
                    it is InferenceEngine.State.Initialized || it is InferenceEngine.State.Error
                }
                if (initialState is InferenceEngine.State.Error) throw initialState.exception
                localEngine.loadModel(model.absolutePath)
                localEngine.setSystemPrompt(SYSTEM_PROMPT)
                engine = localEngine
                bridge = LocalBridgeServer(
                    localEngine,
                    inferenceMutex,
                    checkNotNull(voice),
                    { ears },
                    token,
                    model.name,
                ).also { it.start() }
                updateNotification("Phone conversation model ready")
                Log.i(TAG, "Model service ready with ${model.name}")
            } catch (failure: Exception) {
                Log.e(TAG, "Model service failed", failure)
                updateNotification("Local model needs attention")
            } finally {
                loading = false
            }
        }
    }

    private fun discoverModel(): File? = File(filesDir, "models")
        .listFiles()
        .orEmpty()
        .asSequence()
        .filter { it.isFile && it.extension.equals("gguf", ignoreCase = true) }
        .sortedByDescending {
            when {
                it.name.contains("Qwen3-1.7B", ignoreCase = true) -> 3
                it.name.contains("Qwen3.5-0.8B", ignoreCase = true) -> 2
                it.name.contains("Bonsai-27B-Q1_0", ignoreCase = true) -> 1
                else -> 0
            }
        }
        .firstOrNull()

    private fun createNotificationChannel() {
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_ID,
                "Herbie local brain",
                NotificationManager.IMPORTANCE_LOW,
            ).apply {
                description = "Keeps Herbie's private on-phone conversation model ready"
            },
        )
    }

    private fun notification(text: String): Notification = Notification.Builder(this, CHANNEL_ID)
        .setSmallIcon(android.R.drawable.stat_notify_sync_noanim)
        .setContentTitle("Herbie is running locally")
        .setContentText(text)
        .setOngoing(true)
        .build()

    private fun updateNotification(text: String) {
        getSystemService(NotificationManager::class.java)
            .notify(NOTIFICATION_ID, notification(text))
    }

    override fun onDestroy() {
        bridge?.stop()
        bridge = null
        ears?.stop()
        ears = null
        voice?.shutdown()
        voice = null
        engine?.destroy()
        engine = null
        scope.cancel()
        super.onDestroy()
    }

    companion object {
        private const val TAG = "HerbieModelService"
        private const val CHANNEL_ID = "herbie_local_brain"
        private const val NOTIFICATION_ID = 8766
        private const val PREFERENCES = "herbie_private_bridge"
        private const val TOKEN_KEY = "bridge_token"
        private const val BRAIN_TOKEN_KEY = "brain_token"
        private const val SYSTEM_PROMPT =
            "You are Herbie, a warm local robot companion. Talk naturally, respond directly, " +
                "use contractions, and keep ordinary replies brief. Ask a follow-up only when " +
                "it genuinely helps. Never expose chain-of-thought, analysis, or <think> tags. " +
                "Never claim to move or operate hardware; motor authority is off."
    }
}
