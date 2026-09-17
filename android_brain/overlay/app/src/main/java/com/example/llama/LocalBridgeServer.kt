package com.prismml.herbiebrain

import android.util.Log
import com.arm.aichat.InferenceEngine
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import org.json.JSONObject
import java.io.DataInputStream
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.nio.charset.StandardCharsets
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

/** A token-protected HTTP bridge reachable only from this Android device. */
class LocalBridgeServer(
    private val engine: InferenceEngine,
    private val inferenceMutex: Mutex,
    private val token: String,
    private val modelName: String,
) {
    private val running = AtomicBoolean(false)
    private val workers = Executors.newCachedThreadPool()
    private var serverSocket: ServerSocket? = null
    private var acceptThread: Thread? = null

    fun start() {
        if (!running.compareAndSet(false, true)) return
        val socket = ServerSocket().apply {
            reuseAddress = true
            bind(InetSocketAddress(InetAddress.getByName(HOST), PORT), 8)
        }
        serverSocket = socket
        acceptThread = Thread({ acceptLoop(socket) }, "herbie-model-bridge").apply {
            isDaemon = true
            start()
        }
    }

    fun stop() {
        running.set(false)
        runCatching { serverSocket?.close() }
        serverSocket = null
        workers.shutdownNow()
    }

    private fun acceptLoop(listener: ServerSocket) {
        while (running.get()) {
            try {
                val client = listener.accept()
                workers.execute { handle(client) }
            } catch (error: Exception) {
                if (running.get()) Log.e(TAG, "Bridge accept failed", error)
                if (running.get()) Thread.sleep(100)
            }
        }
    }

    @Suppress("DEPRECATION")
    private fun handle(client: Socket) {
        client.use { socket ->
            socket.soTimeout = 310_000
            try {
                val input = DataInputStream(socket.getInputStream())
                val requestLine = input.readLine() ?: return
                val parts = requestLine.split(' ')
                if (parts.size < 2) return writeJson(socket, 400, error("invalid_request"))
                val method = parts[0]
                val path = parts[1]
                val headers = mutableMapOf<String, String>()
                while (true) {
                    val line = input.readLine() ?: break
                    if (line.isEmpty()) break
                    val separator = line.indexOf(':')
                    if (separator > 0) {
                        headers[line.substring(0, separator).trim().lowercase()] =
                            line.substring(separator + 1).trim()
                    }
                }

                if (method == "GET" && path == "/health") {
                    val body = JSONObject()
                        .put("service", "herbie-phone-model-bridge")
                        .put("version", VERSION)
                        .put("ready", true)
                        .put("model", modelName)
                        .put("local_only", true)
                        .put("motor_authority", false)
                        .put("safe_motion_state", "STOP")
                    return writeJson(socket, 200, body)
                }
                if (method != "POST" || path != "/v1/chat") {
                    return writeJson(socket, 404, error("not_found"))
                }
                if (headers["authorization"] != "Bearer $token") {
                    return writeJson(socket, 401, error("unauthorized"))
                }
                val length = headers["content-length"]?.toIntOrNull() ?: 0
                if (length !in 1..MAX_BODY_BYTES) {
                    return writeJson(socket, 413, error("payload_too_large"))
                }
                val bytes = ByteArray(length)
                input.readFully(bytes)
                val request = JSONObject(String(bytes, StandardCharsets.UTF_8))
                val message = request.optString("message", "").trim()
                val context = request.optString("context", "").trim()
                val maxTokens = request.optInt("max_tokens", 96)
                if (message.isEmpty() || message.length > MAX_MESSAGE_CHARS) {
                    return writeJson(socket, 400, error("invalid_message"))
                }
                if (context.length > MAX_CONTEXT_CHARS || maxTokens !in 1..MAX_OUTPUT_TOKENS) {
                    return writeJson(socket, 400, error("invalid_limits"))
                }

                val directReply =
                    "Reply naturally and directly. Do not show analysis or <think> tags."
                val prompt = if (context.isEmpty()) "$directReply\n\n$message" else
                    "$directReply\n\nHerbie's phone-owned context:\n$context\n\n" +
                        "Current message:\n$message"
                val answer = StringBuilder()
                runBlocking {
                    inferenceMutex.withLock {
                        engine.sendUserPrompt(prompt, predictLength = maxTokens).collect {
                            answer.append(it)
                        }
                    }
                }
                val visibleAnswer = answer.toString()
                    .replace(Regex("(?s)<think>.*?</think>"), "")
                    .replace(Regex("(?s)^\\s*</think>"), "")
                    .trim()
                if (visibleAnswer.isEmpty() || visibleAnswer.startsWith("<think>")) {
                    return writeJson(socket, 503, error("model_returned_no_text"))
                }
                val response = JSONObject()
                    .put("text", visibleAnswer)
                    .put("brain", "phone-local")
                    .put("engine", "llama.cpp-android")
                    .put("model", modelName)
                    .put("local_only", true)
                    .put("motor_authority", false)
                    .put("safe_motion_state", "STOP")
                writeJson(socket, 200, response)
            } catch (failure: Exception) {
                Log.e(TAG, "Bridge request failed", failure)
                runCatching { writeJson(socket, 503, error("inference_unavailable")) }
            }
        }
    }

    private fun error(value: String) = JSONObject().put("error", value)

    private fun writeJson(socket: Socket, status: Int, body: JSONObject) {
        val payload = body.toString().toByteArray(StandardCharsets.UTF_8)
        val reason = when (status) {
            200 -> "OK"
            400 -> "Bad Request"
            401 -> "Unauthorized"
            404 -> "Not Found"
            413 -> "Payload Too Large"
            else -> "Service Unavailable"
        }
        val headers = (
            "HTTP/1.1 $status $reason\r\n" +
                "Content-Type: application/json; charset=utf-8\r\n" +
                "Content-Length: ${payload.size}\r\n" +
                "Cache-Control: no-store\r\n" +
                "Connection: close\r\n\r\n"
            ).toByteArray(StandardCharsets.US_ASCII)
        socket.getOutputStream().apply {
            write(headers)
            write(payload)
            flush()
        }
    }

    companion object {
        private const val HOST = "127.0.0.1"
        private const val PORT = 8766
        private const val VERSION = "0.2.0"
        private const val TAG = "HerbieModelBridge"
        private const val MAX_BODY_BYTES = 32_768
        private const val MAX_MESSAGE_CHARS = 4_000
        private const val MAX_CONTEXT_CHARS = 8_000
        private const val MAX_OUTPUT_TOKENS = 128
    }
}
