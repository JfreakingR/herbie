package com.prismml.herbiebrain

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ImageFormat
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraDevice
import android.hardware.camera2.CameraManager
import android.hardware.camera2.CaptureRequest
import android.media.ImageReader
import android.os.Handler
import android.os.HandlerThread
import android.util.Log
import android.util.Size
import java.io.ByteArrayOutputStream
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

/**
 * Herbie's eyes: one still from the back camera, on request, for his brain to
 * look at. Nothing is stored; the JPEG only lives in memory until it is sent.
 *
 * The camera runs a short preview first so auto-exposure and focus settle -
 * a still taken straight away comes out black, which is what the Termux
 * camera command produced on this phone. The preview goes to an ImageReader
 * that drops every frame: a SurfaceTexture nobody drains fills up and can
 * stall the camera before the still is taken. Blocking; call off the main
 * thread.
 */
class HerbieEyes(private val context: Context) {
    /** True only while the service holds the camera foreground-service type. */
    @Volatile var allowed = false

    @Synchronized
    @SuppressLint("MissingPermission")
    @Suppress("DEPRECATION")
    fun capture(): ByteArray {
        check(allowed) { "camera_not_allowed" }
        val manager = context.getSystemService(CameraManager::class.java)
        val cameraId = manager.cameraIdList.firstOrNull { id ->
            manager.getCameraCharacteristics(id).get(CameraCharacteristics.LENS_FACING) ==
                CameraCharacteristics.LENS_FACING_BACK
        } ?: manager.cameraIdList.first()
        val characteristics = manager.getCameraCharacteristics(cameraId)
        val formats = checkNotNull(
            characteristics.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP),
        ) { "no_stream_configuration" }
        val stillSize = pickSize(formats.getOutputSizes(ImageFormat.JPEG), MAX_CAPTURE_WIDTH)
        val previewSize = pickSize(formats.getOutputSizes(ImageFormat.YUV_420_888), PREVIEW_WIDTH)

        val thread = HandlerThread("herbie-eyes").apply { start() }
        val handler = Handler(thread.looper)
        val reader = ImageReader.newInstance(stillSize.width, stillSize.height, ImageFormat.JPEG, 2)
        val preview = ImageReader.newInstance(
            previewSize.width, previewSize.height, ImageFormat.YUV_420_888, 3,
        )
        preview.setOnImageAvailableListener({ source ->
            source.acquireLatestImage()?.close()
        }, handler)
        val previewSurface = preview.surface
        val jpeg = AtomicReference<ByteArray?>()
        val failure = AtomicReference<String?>()
        val done = CountDownLatch(1)
        var device: CameraDevice? = null
        var session: CameraCaptureSession? = null

        reader.setOnImageAvailableListener({ source ->
            val image = source.acquireLatestImage() ?: return@setOnImageAvailableListener
            try {
                val buffer = image.planes[0].buffer
                jpeg.set(ByteArray(buffer.remaining()).also { buffer.get(it) })
            } finally {
                image.close()
            }
            done.countDown()
        }, handler)

        fun fail(reason: String) {
            failure.compareAndSet(null, reason)
            done.countDown()
        }

        try {
            manager.openCamera(cameraId, object : CameraDevice.StateCallback() {
                override fun onOpened(camera: CameraDevice) {
                    device = camera
                    camera.createCaptureSession(
                        listOf(previewSurface, reader.surface),
                        object : CameraCaptureSession.StateCallback() {
                            override fun onConfigured(configured: CameraCaptureSession) {
                                session = configured
                                try {
                                    val warmUp = camera.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW)
                                    warmUp.addTarget(previewSurface)
                                    warmUp.set(CaptureRequest.CONTROL_MODE, CaptureRequest.CONTROL_MODE_AUTO)
                                    configured.setRepeatingRequest(warmUp.build(), null, handler)
                                } catch (error: Exception) {
                                    fail("preview_failed")
                                    return
                                }
                                handler.postDelayed({
                                    try {
                                        val still = camera.createCaptureRequest(CameraDevice.TEMPLATE_STILL_CAPTURE)
                                        still.addTarget(reader.surface)
                                        still.set(CaptureRequest.CONTROL_MODE, CaptureRequest.CONTROL_MODE_AUTO)
                                        still.set(CaptureRequest.JPEG_QUALITY, JPEG_QUALITY.toByte())
                                        still.set(
                                            CaptureRequest.JPEG_ORIENTATION,
                                            characteristics.get(CameraCharacteristics.SENSOR_ORIENTATION) ?: 0,
                                        )
                                        configured.capture(still.build(), null, handler)
                                    } catch (error: Exception) {
                                        fail("capture_failed")
                                    }
                                }, WARM_UP_MS)
                            }

                            override fun onConfigureFailed(configured: CameraCaptureSession) {
                                fail("configure_failed")
                            }
                        },
                        handler,
                    )
                }

                override fun onDisconnected(camera: CameraDevice) = fail("camera_disconnected")

                override fun onError(camera: CameraDevice, error: Int) = fail("camera_error_$error")
            }, handler)

            if (!done.await(TIMEOUT_SECONDS, TimeUnit.SECONDS)) error("camera_timeout")
            failure.get()?.let { error(it) }
            Log.i(TAG, "Took a photo")
            return shrink(jpeg.get() ?: error("no_image"))
        } finally {
            runCatching { session?.close() }
            runCatching { device?.close() }
            runCatching { reader.close() }
            runCatching { preview.close() }
            thread.quitSafely()
        }
    }

    /** The largest size no wider than `limit`, else the smallest available. */
    private fun pickSize(sizes: Array<Size>, limit: Int): Size =
        sizes.filter { it.width <= limit }.maxByOrNull { it.width.toLong() * it.height }
            ?: sizes.minBy { it.width.toLong() * it.height }

    /** Re-encode so the longest edge is at most MAX_EDGE: small enough to send. */
    private fun shrink(original: ByteArray): ByteArray {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(original, 0, original.size, bounds)
        var sample = 1
        while (maxOf(bounds.outWidth, bounds.outHeight) / (sample * 2) >= MAX_EDGE) sample *= 2
        val decoded = BitmapFactory.decodeByteArray(
            original, 0, original.size, BitmapFactory.Options().apply { inSampleSize = sample },
        ) ?: return original
        val longest = maxOf(decoded.width, decoded.height)
        val scaled = if (longest > MAX_EDGE) {
            val factor = MAX_EDGE.toFloat() / longest
            Bitmap.createScaledBitmap(
                decoded, (decoded.width * factor).toInt(), (decoded.height * factor).toInt(), true,
            )
        } else decoded
        return ByteArrayOutputStream().use { out ->
            scaled.compress(Bitmap.CompressFormat.JPEG, JPEG_QUALITY, out)
            out.toByteArray()
        }
    }

    companion object {
        private const val MAX_CAPTURE_WIDTH = 2048
        private const val PREVIEW_WIDTH = 640
        private const val MAX_EDGE = 1280
        private const val JPEG_QUALITY = 85
        private const val WARM_UP_MS = 1_200L
        private const val TIMEOUT_SECONDS = 10L
        private const val TAG = "HerbieEyes"
    }
}
