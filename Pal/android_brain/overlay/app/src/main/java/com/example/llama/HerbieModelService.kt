package com.prismml.herbiebrain

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
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
    @Volatile private var loading = false

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, notification("Starting local conversation model…"))
        startModelIfNeeded()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startModelIfNeeded()
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

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
        private const val SYSTEM_PROMPT =
            "You are Herbie, a warm local robot companion. Talk naturally, respond directly, " +
                "use contractions, and keep ordinary replies brief. Ask a follow-up only when " +
                "it genuinely helps. Never expose chain-of-thought, analysis, or <think> tags. " +
                "Never claim to move or operate hardware; motor authority is off."
    }
}
