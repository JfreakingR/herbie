package com.prismml.herbiebrain

import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.util.Base64
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.EditText
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.activity.addCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.arm.aichat.AiChat
import com.arm.aichat.InferenceEngine
import com.arm.aichat.gguf.GgufMetadata
import com.arm.aichat.gguf.GgufMetadataReader
import com.google.android.material.button.MaterialButton
import com.google.android.material.floatingactionbutton.FloatingActionButton
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onCompletion
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.io.File
import java.io.FileOutputStream
import java.io.InputStream
import java.util.UUID

class MainActivity : AppCompatActivity() {

    private lateinit var statusTv: TextView
    private lateinit var messagesRv: RecyclerView
    private lateinit var userInputEt: EditText
    private lateinit var userActionFab: FloatingActionButton
    private lateinit var pickModelButton: MaterialButton
    private lateinit var benchmarkButton: MaterialButton
    private lateinit var progress: ProgressBar

    private lateinit var engine: InferenceEngine
    private var generationJob: Job? = null
    private var isModelReady = false
    private var loadedModel: File? = null
    private var pendingPrompt: String? = null
    private var bridgeToken: String? = null
    private val inferenceMutex = Mutex()

    private val messages = mutableListOf<Message>()
    private val lastAssistantMsg = StringBuilder()
    private val messageAdapter = MessageAdapter(messages)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        pendingPrompt = decodePrompt(intent)
        bridgeToken = decodeBridgeToken(intent)
        onBackPressedDispatcher.addCallback { moveTaskToBack(true) }

        statusTv = findViewById(R.id.gguf)
        messagesRv = findViewById(R.id.messages)
        messagesRv.layoutManager = LinearLayoutManager(this).apply { stackFromEnd = true }
        messagesRv.adapter = messageAdapter
        userInputEt = findViewById(R.id.user_input)
        userActionFab = findViewById(R.id.fab)
        pickModelButton = findViewById(R.id.pick_model)
        benchmarkButton = findViewById(R.id.benchmark)
        progress = findViewById(R.id.progress)

        ensureModelsDirectory()
        ensureExternalModelsDirectory()

        userActionFab.setOnClickListener { if (isModelReady) handleUserInput() }
        pickModelButton.setOnClickListener { getContent.launch(arrayOf("*/*")) }
        benchmarkButton.setOnClickListener { if (isModelReady) runBenchmark() }
        userInputEt.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_SEND && isModelReady) {
                handleUserInput()
                true
            } else false
        }

        if (bridgeToken != null) {
            startBridgeIfConfigured()
            setBusy(false)
            statusTv.text = "Herbie's private local model service is starting…"
            userInputEt.isEnabled = false
            userActionFab.isEnabled = false
            benchmarkButton.isEnabled = false
            return
        }

        lifecycleScope.launch(Dispatchers.Default) {
            try {
                engine = AiChat.getInferenceEngine(applicationContext)
                val initialState = engine.state.first {
                    it is InferenceEngine.State.Initialized || it is InferenceEngine.State.Error
                }
                if (initialState is InferenceEngine.State.Error) throw initialState.exception

                val existing = discoverExistingModel()
                if (existing != null) {
                    loadModel(existing.name, existing)
                } else {
                    withContext(Dispatchers.Main) {
                        setBusy(false)
                        statusTv.text = "Движок готов. Выберите Bonsai-27B-Q1_0.gguf (3,80 ГБ)."
                    }
                }
            } catch (e: Exception) {
                showError("Ошибка инициализации", e)
            }
        }
    }

    private val getContent = registerForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri ->
        Log.i(TAG, "Selected file uri: $uri")
        uri?.let { handleSelectedModel(it) }
    }

    private fun handleSelectedModel(uri: Uri) {
        setBusy(true, "Проверяю GGUF…")
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val metadata = contentResolver.openInputStream(uri)?.use {
                    GgufMetadataReader.create().readStructuredMetadata(it)
                } ?: error("Не удалось открыть выбранный файл")

                val modelName = metadata.filename() + FILE_EXTENSION_GGUF
                val modelFile = contentResolver.openInputStream(uri)?.use { input ->
                    ensureModelFile(modelName, input)
                } ?: error("Не удалось скопировать модель")
                loadModel(modelName, modelFile)
            } catch (e: Exception) {
                showError("Не удалось загрузить GGUF", e)
            }
        }
    }

    private suspend fun ensureModelFile(modelName: String, input: InputStream) =
        withContext(Dispatchers.IO) {
            File(ensureModelsDirectory(), modelName).also { file ->
                if (!file.exists() || file.length() == 0L) {
                    withContext(Dispatchers.Main) {
                        setBusy(true, "Копирую модель во внутреннее хранилище…")
                    }
                    FileOutputStream(file).use { output -> input.copyTo(output, 8 * 1024 * 1024) }
                }
            }
        }

    private suspend fun loadModel(modelName: String, modelFile: File) {
        withContext(Dispatchers.Main) {
            setBusy(true, "Загружаю $modelName в память…")
        }
        engine.loadModel(modelFile.absolutePath)
        engine.setSystemPrompt(
            """You are Herbie, a warm local robot companion. Talk like a natural person: """ +
                """respond directly, use contractions, keep ordinary replies brief, and ask a """ +
                """follow-up only when it genuinely helps. Never expose chain-of-thought, analysis, """ +
                """or <think> tags. Do not claim to move or operate hardware; motor authority is off. """ +
                """Use the user's language."""
        )
        loadedModel = modelFile
        isModelReady = true
        withContext(Dispatchers.Main) {
            val gib = modelFile.length().toDouble() / (1024.0 * 1024.0 * 1024.0)
            statusTv.text = "● Локально · $modelName · %.2f GiB · ${Build.SUPPORTED_ABIS.first()}".format(gib)
            userInputEt.hint = "Сообщение для Bonsai…"
            userInputEt.isEnabled = true
            userActionFab.isEnabled = true
            benchmarkButton.isEnabled = true
            setBusy(false)
            addAssistantMessage("Модель загружена на устройстве. Интернет для диалога не используется.")
            startBridgeIfConfigured()
            pendingPrompt?.let { prompt ->
                pendingPrompt = null
                userInputEt.setText(prompt)
                handleUserInput()
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        decodeBridgeToken(intent)?.let { token ->
            bridgeToken = token
            startBridgeIfConfigured()
        }
        decodePrompt(intent)?.let { prompt ->
            if (isModelReady) {
                userInputEt.setText(prompt)
                handleUserInput()
            } else {
                pendingPrompt = prompt
            }
        }
    }

    private fun decodePrompt(intent: Intent): String? =
        intent.getStringExtra(EXTRA_PROMPT_BASE64)?.let { encoded ->
            runCatching {
                String(Base64.decode(encoded, Base64.NO_WRAP), Charsets.UTF_8)
            }.getOrNull()
        }

    private fun decodeBridgeToken(intent: Intent): String? {
        val supplied = intent.getStringExtra(EXTRA_BRIDGE_TOKEN)
            ?.trim()
            ?.takeIf { it.length >= 16 }
        if (supplied != null) {
            getSharedPreferences(BRIDGE_PREFERENCES, MODE_PRIVATE)
                .edit()
                .putString(EXTRA_BRIDGE_TOKEN, supplied)
                .apply()
            return supplied
        }
        return getSharedPreferences(BRIDGE_PREFERENCES, MODE_PRIVATE)
            .getString(EXTRA_BRIDGE_TOKEN, null)
            ?.trim()
            ?.takeIf { it.length >= 16 }
    }

    private fun startBridgeIfConfigured() {
        bridgeToken ?: return
        ContextCompat.startForegroundService(
            this,
            Intent(this, HerbieModelService::class.java),
        )
        Log.i(TAG, "Herbie foreground model service requested")
    }

    private fun handleUserInput() {
        val userMsg = userInputEt.text.toString().trim()
        if (userMsg.isEmpty()) {
            Toast.makeText(this, "Введите сообщение", Toast.LENGTH_SHORT).show()
            return
        }

        userInputEt.text = null
        userInputEt.isEnabled = false
        userActionFab.isEnabled = false
        benchmarkButton.isEnabled = false
        messages.add(Message(UUID.randomUUID().toString(), userMsg, true))
        lastAssistantMsg.clear()
        messages.add(Message(UUID.randomUUID().toString(), "", false))
        messageAdapter.notifyItemRangeInserted(messages.size - 2, 2)
        messagesRv.scrollToPosition(messages.size - 1)

        generationJob = lifecycleScope.launch(Dispatchers.Default) {
            inferenceMutex.withLock {
                engine.sendUserPrompt(userMsg, predictLength = 256)
                    .onCompletion {
                        withContext(Dispatchers.Main) {
                            userInputEt.isEnabled = true
                            userActionFab.isEnabled = true
                            benchmarkButton.isEnabled = true
                        }
                    }
                    .collect { token ->
                        withContext(Dispatchers.Main) {
                            val last = messages.lastIndex
                            messages[last] = messages[last].copy(
                                content = lastAssistantMsg.append(token).toString()
                            )
                            messageAdapter.notifyItemChanged(last)
                            messagesRv.scrollToPosition(last)
                        }
                    }
            }
        }
    }

    private fun runBenchmark() {
        setBusy(true, "Измеряю скорость на этом Android-устройстве…")
        userInputEt.isEnabled = false
        userActionFab.isEnabled = false
        benchmarkButton.isEnabled = false
        lifecycleScope.launch(Dispatchers.Default) {
            try {
                val result = engine.bench(pp = 64, tg = 32, pl = 1, nr = 1)
                withContext(Dispatchers.Main) {
                    addAssistantMessage("Тест скорости (pp64 / tg32):\n\n$result")
                }
            } catch (e: Exception) {
                showError("Тест скорости завершился с ошибкой", e)
            } finally {
                withContext(Dispatchers.Main) {
                    setBusy(false)
                    userInputEt.isEnabled = true
                    userActionFab.isEnabled = true
                    benchmarkButton.isEnabled = true
                    loadedModel?.let { statusTv.text = "● Локально · ${it.name} · готово" }
                }
            }
        }
    }

    private fun discoverExistingModel(): File? {
        val candidates = buildList {
            add(ensureModelsDirectory())
            add(ensureExternalModelsDirectory())
        }
        return candidates.asSequence()
            .flatMap { it.listFiles().orEmpty().asSequence() }
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
    }

    private fun ensureModelsDirectory() =
        File(filesDir, DIRECTORY_MODELS).also { if (!it.exists()) it.mkdirs() }

    private fun ensureExternalModelsDirectory() =
        File(getExternalFilesDir(null) ?: filesDir, DIRECTORY_MODELS).also {
            if (!it.exists()) it.mkdirs()
        }

    private fun setBusy(busy: Boolean, message: String? = null) {
        progress.visibility = if (busy) View.VISIBLE else View.INVISIBLE
        pickModelButton.isEnabled = !busy
        message?.let { statusTv.text = it }
    }

    private fun addAssistantMessage(text: String) {
        messages.add(Message(UUID.randomUUID().toString(), text, false))
        messageAdapter.notifyItemInserted(messages.lastIndex)
        messagesRv.scrollToPosition(messages.lastIndex)
    }

    private suspend fun showError(title: String, error: Throwable) {
        Log.e(TAG, title, error)
        withContext(Dispatchers.Main) {
            isModelReady = false
            setBusy(false)
            statusTv.text = "$title: ${error.message ?: error.javaClass.simpleName}"
            Toast.makeText(this@MainActivity, statusTv.text, Toast.LENGTH_LONG).show()
        }
    }

    override fun onStop() {
        generationJob?.cancel()
        super.onStop()
    }

    override fun onDestroy() {
        if (::engine.isInitialized) engine.destroy()
        super.onDestroy()
    }

    companion object {
        private val TAG = MainActivity::class.java.simpleName
        private const val DIRECTORY_MODELS = "models"
        private const val FILE_EXTENSION_GGUF = ".gguf"
        private const val EXTRA_PROMPT_BASE64 = "prompt_b64"
        private const val EXTRA_BRIDGE_TOKEN = "bridge_token"
        private const val BRIDGE_PREFERENCES = "herbie_private_bridge"
    }
}

fun GgufMetadata.filename() = when {
    basic.name != null -> basic.name?.let { name ->
        basic.sizeLabel?.let { size -> "$name-$size" } ?: name
    }
    architecture?.architecture != null -> architecture?.architecture?.let { arch ->
        basic.uuid?.let { uuid -> "$arch-$uuid" } ?: "$arch-${System.currentTimeMillis()}"
    }
    else -> "model-${System.currentTimeMillis()}"
}
