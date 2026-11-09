package com.aman.grain

import android.Manifest
import android.app.Activity
import android.content.ContentValues
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.ImageFormat
import android.graphics.Matrix
import android.graphics.RectF
import android.graphics.SurfaceTexture
import android.hardware.camera2.CameraAccessException
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraDevice
import android.hardware.camera2.CameraManager
import android.hardware.camera2.CameraMetadata
import android.hardware.camera2.CaptureRequest
import android.hardware.camera2.CaptureFailure
import android.hardware.camera2.DngCreator
import android.hardware.camera2.TotalCaptureResult
import android.media.Image
import android.media.ImageReader
import android.media.ExifInterface
import android.media.MediaRecorder
import android.net.Uri
import android.os.Environment
import android.os.Handler
import android.os.HandlerThread
import android.provider.MediaStore
import android.util.Range
import android.util.Size
import android.view.Surface
import android.view.TextureView
import java.io.File
import java.io.FileInputStream
import java.io.OutputStream
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.Executors
import kotlin.math.abs

data class CameraCapabilities(
    val raw: Boolean,
    val manualSensor: Boolean,
    val minIso: Int,
    val maxIso: Int,
    val minExposureNs: Long,
    val maxExposureNs: Long,
    val minFocusDistance: Float
)

class CameraEngine(
    private val activity: Activity,
    private val previewView: TextureView,
    private val listener: Listener
) {
    interface Listener {
        fun onStatus(message: String)
        fun onCapabilities(capabilities: CameraCapabilities)
        fun onPhotoSaved(message: String)
        fun onRecordingChanged(recording: Boolean)
        fun onError(message: String)
    }

    private val cameraManager =
        activity.getSystemService(Context.CAMERA_SERVICE) as CameraManager
    private val saveExecutor = Executors.newSingleThreadExecutor()

    private companion object {
        const val MAX_JPEG_PIXELS = 14_000_000L
        const val MAX_RAW_PIXELS = 24_000_000L
    }

    private var cameraThread: HandlerThread? = null
    private var cameraHandler: Handler? = null
    private var cameraDevice: CameraDevice? = null
    private var captureSession: CameraCaptureSession? = null
    private var previewSurface: Surface? = null
    private var previewBuilder: CaptureRequest.Builder? = null
    private var characteristics: CameraCharacteristics? = null
    private var jpegReader: ImageReader? = null
    private var rawReader: ImageReader? = null

    private var previewSize = Size(1280, 720)
    private var jpegSize = Size(4000, 3000)
    private var rawSize = Size(4000, 3000)

    private var rawAdvertised = false
    private var rawSessionActive = false
    private var manualSensor = false
    private var frontFacing = false
    private var opening = false
    private var recording = false
    private var videoRecorder: MediaRecorder? = null
    private var videoFile: File? = null

    private var manualExposureEnabled = false
    private var manualIso = 100
    private var manualExposureNs = 10_000_000L
    private var manualFocusDistance: Float? = null
    private var whiteBalanceMode = CaptureRequest.CONTROL_AWB_MODE_AUTO
    private var flashEnabled = false
    private var selectedAspectRatio = 4f / 3f
    private var exposureCompensation = 0

    private val pendingLock = Any()
    private var pendingJpeg: Image? = null
    private var pendingRaw: Image? = null
    private var pendingResult: TotalCaptureResult? = null
    private var pendingFilter = FilterPreset.ORIGINAL
    private var pendingNeedsRaw = false
    private var captureInProgress = false

    fun start() {
        if (cameraDevice != null || opening) return
        startCameraThread()
        openSelectedCamera()
    }

    fun stop() {
        if (recording) stopVideoImmediately()
        closeCameraResources()
        saveExecutor.shutdown()
        cameraThread?.quitSafely()
        cameraThread = null
        cameraHandler = null
        opening = false
    }

    fun flipCamera() {
        cameraHandler?.post {
            frontFacing = !frontFacing
            closeCameraResources()
            openSelectedCamera()
        }
    }

    fun setFlash(enabled: Boolean) {
        flashEnabled = enabled
        updatePreview()
    }

    fun setAspectRatio(ratio: Float) {
        selectedAspectRatio = if (ratio > 0f) ratio else 0f
        configureTransform(previewView.width, previewView.height)
        listener.onStatus(
            if (selectedAspectRatio == 0f) "Full sensor framing selected"
            else "Frame set to " + String.format(Locale.US, "%.2f:1", selectedAspectRatio)
        )
    }

    fun desiredOutputAspectRatio(): Float {
        if (selectedAspectRatio <= 0f) return 0f
        val portrait = previewView.height >= previewView.width
        return if (portrait) 1f / selectedAspectRatio else selectedAspectRatio
    }

    fun configureTransform(viewWidth: Int, viewHeight: Int) {
        if (viewWidth <= 0 || viewHeight <= 0) return
        val chars = characteristics ?: return
        val sensorOrientation =
            chars.get(CameraCharacteristics.SENSOR_ORIENTATION) ?: 90
        val rotation = activity.windowManager.defaultDisplay.rotation
        val displayDegrees = when (rotation) {
            Surface.ROTATION_0 -> 0
            Surface.ROTATION_90 -> 90
            Surface.ROTATION_180 -> 180
            else -> 270
        }
        val front = chars.get(CameraCharacteristics.LENS_FACING) ==
            CameraCharacteristics.LENS_FACING_FRONT
        val relativeRotation = if (front) {
            (sensorOrientation + displayDegrees) % 360
        } else {
            (sensorOrientation - displayDegrees + 360) % 360
        }

        val rotatedWidth = if (relativeRotation == 90 || relativeRotation == 270) {
            previewSize.height.toFloat()
        } else {
            previewSize.width.toFloat()
        }
        val rotatedHeight = if (relativeRotation == 90 || relativeRotation == 270) {
            previewSize.width.toFloat()
        } else {
            previewSize.height.toFloat()
        }
        val scale = maxOf(
            viewWidth.toFloat() / rotatedWidth,
            viewHeight.toFloat() / rotatedHeight
        )
        val centerX = viewWidth / 2f
        val centerY = viewHeight / 2f
        val matrix = Matrix().apply {
            setTranslate(
                centerX - previewSize.width / 2f,
                centerY - previewSize.height / 2f
            )
            postRotate(relativeRotation.toFloat(), centerX, centerY)
            postScale(scale, scale, centerX, centerY)
        }
        previewView.setTransform(matrix)
    }

    fun setExposureCompensation(steps: Int) {
        val range = characteristics?.get(
            CameraCharacteristics.CONTROL_AE_COMPENSATION_RANGE
        ) ?: return
        exposureCompensation = steps.coerceIn(range.lower, range.upper)
        updatePreview()
    }

    fun setManualMode(enabled: Boolean) {
        manualExposureEnabled = enabled && manualSensor
        updatePreview()
    }

    fun setManualExposure(iso: Int, exposureNs: Long) {
        val chars = characteristics ?: return
        val isoRange = chars.get(CameraCharacteristics.SENSOR_INFO_SENSITIVITY_RANGE)
        val exposureRange = chars.get(CameraCharacteristics.SENSOR_INFO_EXPOSURE_TIME_RANGE)
        manualIso = isoRange?.let { iso.coerceIn(it.lower, it.upper) } ?: iso
        manualExposureNs = exposureRange?.let {
            exposureNs.coerceIn(it.lower, it.upper)
        } ?: exposureNs
        manualExposureEnabled = manualSensor
        updatePreview()
    }

    fun setManualFocus(distance: Float) {
        val chars = characteristics ?: return
        val maximum = chars.get(CameraCharacteristics.LENS_INFO_MINIMUM_FOCUS_DISTANCE) ?: 0f
        if (maximum <= 0f) return
        manualFocusDistance = distance.coerceIn(0f, maximum)
        updatePreview()
    }

    fun setWhiteBalance(name: String) {
        val requested = when (name.lowercase(Locale.US)) {
            "daylight" -> CaptureRequest.CONTROL_AWB_MODE_DAYLIGHT
            "cloudy" -> CaptureRequest.CONTROL_AWB_MODE_CLOUDY_DAYLIGHT
            "tungsten" -> CaptureRequest.CONTROL_AWB_MODE_INCANDESCENT
            "fluorescent" -> CaptureRequest.CONTROL_AWB_MODE_FLUORESCENT
            else -> CaptureRequest.CONTROL_AWB_MODE_AUTO
        }
        val available = characteristics?.get(
            CameraCharacteristics.CONTROL_AWB_AVAILABLE_MODES
        ) ?: intArrayOf(CaptureRequest.CONTROL_AWB_MODE_AUTO)
        whiteBalanceMode = if (available.contains(requested)) {
            requested
        } else {
            CaptureRequest.CONTROL_AWB_MODE_AUTO
        }
        updatePreview()
        if (whiteBalanceMode != requested) {
            listener.onStatus("That white balance preset is not supported by this lens")
        }
    }

    fun takePhoto(filter: FilterPreset) {
        val device = cameraDevice ?: return
        val session = captureSession ?: return
        val jpeg = jpegReader ?: return
        if (recording || captureInProgress) return

        synchronized(pendingLock) {
            pendingJpeg?.close()
            pendingRaw?.close()
            pendingJpeg = null
            pendingRaw = null
            pendingResult = null
            pendingFilter = filter
            pendingNeedsRaw = rawSessionActive
            captureInProgress = true
        }

        try {
            val request = device.createCaptureRequest(CameraDevice.TEMPLATE_STILL_CAPTURE)
            request.addTarget(jpeg.surface)
            if (rawSessionActive) rawReader?.surface?.let { request.addTarget(it) }
            applyControls(request, still = true)
            request.set(CaptureRequest.JPEG_ORIENTATION, jpegOrientation())

            session.capture(request.build(), object : CameraCaptureSession.CaptureCallback() {
                override fun onCaptureCompleted(
                    session: CameraCaptureSession,
                    request: CaptureRequest,
                    result: TotalCaptureResult
                ) {
                    synchronized(pendingLock) {
                        pendingResult = result
                        finishPendingCapture()
                    }
                }

                override fun onCaptureFailed(
                    session: CameraCaptureSession,
                    request: CaptureRequest,
                    failure: CaptureFailure
                ) {
                    synchronized(pendingLock) {
                        captureInProgress = false
                        pendingJpeg?.close()
                        pendingRaw?.close()
                        pendingJpeg = null
                        pendingRaw = null
                        pendingResult = null
                    }
                    listener.onError("Capture failed. Try again.")
                }
            }, cameraHandler)
            listener.onStatus("Capturing…")
        } catch (error: Exception) {
            synchronized(pendingLock) { captureInProgress = false }
            listener.onError("Camera capture error: " + (error.message ?: "unknown"))
        }
    }

    fun startVideo(withAudio: Boolean) {
        val device = cameraDevice ?: return
        val handler = cameraHandler ?: return
        if (recording) return

        handler.post {
            try {
                captureSession?.close()
                captureSession = null

                val map = characteristics?.get(
                    CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP
                )
                val videoSizes = map?.getOutputSizes(MediaRecorder::class.java)?.toList().orEmpty()
                val chosen = videoSizes
                    .filter { it.width <= 1920 && it.height <= 1080 }
                    .maxByOrNull { it.width.toLong() * it.height.toLong() }
                    ?: previewSize

                val file = File.createTempFile("grain-video-", ".mp4", activity.cacheDir)
                val recorder = MediaRecorder()
                if (withAudio) recorder.setAudioSource(MediaRecorder.AudioSource.MIC)
                recorder.setVideoSource(MediaRecorder.VideoSource.SURFACE)
                recorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
                recorder.setOutputFile(file.absolutePath)
                if (withAudio) {
                    recorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
                    recorder.setAudioEncodingBitRate(128_000)
                    recorder.setAudioSamplingRate(44_100)
                }
                recorder.setVideoEncoder(MediaRecorder.VideoEncoder.H264)
                recorder.setVideoEncodingBitRate(8_000_000)
                recorder.setVideoFrameRate(30)
                recorder.setVideoSize(chosen.width, chosen.height)
                recorder.setOrientationHint(jpegOrientation())
                recorder.prepare()

                videoFile = file
                videoRecorder = recorder
                val preview = previewSurface
                    ?: throw IllegalStateException("Preview surface is unavailable")

                device.createCaptureSession(
                    listOf(preview, recorder.surface),
                    object : CameraCaptureSession.StateCallback() {
                        override fun onConfigured(session: CameraCaptureSession) {
                            captureSession = session
                            try {
                                val request = device.createCaptureRequest(
                                    CameraDevice.TEMPLATE_RECORD
                                )
                                request.addTarget(preview)
                                request.addTarget(recorder.surface)
                                applyControls(request, still = false)
                                session.setRepeatingRequest(request.build(), null, cameraHandler)
                                recorder.start()
                                recording = true
                                listener.onRecordingChanged(true)
                                listener.onStatus("Recording video")
                            } catch (error: Exception) {
                                listener.onError("Could not start video: " + error.message)
                                stopVideoImmediately()
                            }
                        }

                        override fun onConfigureFailed(session: CameraCaptureSession) {
                            listener.onError("This camera could not configure video recording.")
                            stopVideoImmediately()
                            configurePreviewSession(rawSessionActive)
                        }
                    },
                    handler
                )
            } catch (error: Exception) {
                listener.onError("Video setup failed: " + (error.message ?: "unknown"))
                stopVideoImmediately()
                configurePreviewSession(rawSessionActive)
            }
        }
    }

    fun stopVideo() {
        cameraHandler?.post { stopVideoImmediately() }
    }

    private fun stopVideoImmediately() {
        val recorder = videoRecorder
        val file = videoFile

        try {
            if (recording && recorder != null) recorder.stop()
        } catch (_: RuntimeException) {
            file?.delete()
        } finally {
            try {
                recorder?.reset()
                recorder?.release()
            } catch (_: Exception) {
            }
            videoRecorder = null
            videoFile = null
            val wasRecording = recording
            recording = false
            if (wasRecording) listener.onRecordingChanged(false)
        }

        if (file != null && file.exists() && file.length() > 0L) {
            saveExecutor.execute { saveVideo(file) }
        }
        if (cameraDevice != null && cameraHandler != null) {
            configurePreviewSession(rawSessionActive)
        }
    }

    private fun saveVideo(file: File) {
        try {
            val stamp = timestamp()
            writeToMediaStore(
                MediaStore.Video.Media.EXTERNAL_CONTENT_URI,
                "GRAIN_" + stamp + ".mp4",
                "video/mp4"
            ) { output ->
                FileInputStream(file).use { input -> input.copyTo(output) }
            }
            file.delete()
            listener.onStatus("Video saved to DCIM/Grain Camera")
        } catch (error: Exception) {
            listener.onError("Could not save video: " + (error.message ?: "unknown"))
        }
    }

    private fun startCameraThread() {
        if (cameraThread != null) return
        val thread = HandlerThread("GrainCamera")
        thread.start()
        cameraThread = thread
        cameraHandler = Handler(thread.looper)
    }

    private fun openSelectedCamera() {
        if (activity.checkSelfPermission(Manifest.permission.CAMERA) !=
            PackageManager.PERMISSION_GRANTED
        ) return

        try {
            val candidates = cameraManager.cameraIdList.mapNotNull { id ->
                val chars = cameraManager.getCameraCharacteristics(id)
                val facing = chars.get(CameraCharacteristics.LENS_FACING)
                val wanted = if (frontFacing) CameraCharacteristics.LENS_FACING_FRONT
                    else CameraCharacteristics.LENS_FACING_BACK
                if (facing == wanted) Pair(id, chars) else null
            }

            if (candidates.isEmpty()) {
                listener.onError("No camera was found for the selected direction.")
                return
            }

            val selected = candidates.maxByOrNull { pair ->
                val caps = pair.second.get(
                    CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES
                ) ?: intArrayOf()
                val rawScore = if (caps.contains(
                        CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES_RAW
                    )
                ) 1_000_000_000L else 0L
                val pixels = pair.second.get(
                    CameraCharacteristics.SENSOR_INFO_PIXEL_ARRAY_SIZE
                )?.let { it.width.toLong() * it.height.toLong() } ?: 0L
                rawScore + pixels
            } ?: candidates.first()

            characteristics = selected.second
            val caps = selected.second.get(
                CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES
            ) ?: intArrayOf()
            rawAdvertised = caps.contains(
                CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES_RAW
            )
            manualSensor = caps.contains(
                CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES_MANUAL_SENSOR
            )

            configureSizes(selected.second)
            prepareReaders()

            val isoRange = selected.second.get(
                CameraCharacteristics.SENSOR_INFO_SENSITIVITY_RANGE
            ) ?: Range(50, 800)
            val exposureRange = selected.second.get(
                CameraCharacteristics.SENSOR_INFO_EXPOSURE_TIME_RANGE
            ) ?: Range(125_000L, 1_000_000_000L)
            val focus = selected.second.get(
                CameraCharacteristics.LENS_INFO_MINIMUM_FOCUS_DISTANCE
            ) ?: 0f

            listener.onCapabilities(
                CameraCapabilities(
                    rawAdvertised,
                    manualSensor,
                    isoRange.lower,
                    isoRange.upper,
                    exposureRange.lower,
                    exposureRange.upper,
                    focus
                )
            )

            opening = true
            cameraManager.openCamera(selected.first, object : CameraDevice.StateCallback() {
                override fun onOpened(camera: CameraDevice) {
                    opening = false
                    cameraDevice = camera
                    configurePreviewSession(rawAdvertised)
                }

                override fun onDisconnected(camera: CameraDevice) {
                    opening = false
                    camera.close()
                    if (cameraDevice == camera) cameraDevice = null
                    listener.onStatus("Camera disconnected")
                }

                override fun onError(camera: CameraDevice, error: Int) {
                    opening = false
                    camera.close()
                    if (cameraDevice == camera) cameraDevice = null
                    listener.onError("Camera could not open (code " + error + ").")
                }
            }, cameraHandler)
        } catch (error: CameraAccessException) {
            opening = false
            listener.onError("Camera access error: " + (error.message ?: "unknown"))
        } catch (error: Exception) {
            opening = false
            listener.onError("Camera setup error: " + (error.message ?: "unknown"))
        }
    }

    private fun configureSizes(chars: CameraCharacteristics) {
        val map = chars.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP)
        val previewSizes = map?.getOutputSizes(SurfaceTexture::class.java)?.toList().orEmpty()
        if (previewSizes.isNotEmpty()) {
            previewSize = previewSizes
                .filter { it.width <= 1920 && it.height <= 1080 }
                .minByOrNull {
                    val aspect = it.width.toDouble() / it.height.toDouble()
                    abs(aspect - (16.0 / 9.0)) * 100_000.0 +
                        abs(it.width * it.height - 1280 * 720).toDouble()
                } ?: previewSizes.minByOrNull {
                    it.width.toLong() * it.height.toLong()
                } ?: previewSizes.first()
        }

        // Keep the app memory-safe on high-megapixel devices such as the S23 Ultra.
        // Prefer a sensor output <= 14 MP for JPEG and <= 24 MP for DNG.
        val jpegSizes = map?.getOutputSizes(ImageFormat.JPEG)?.toList().orEmpty()
        val safeJpegSizes = jpegSizes.filter {
            it.width.toLong() * it.height.toLong() <= MAX_JPEG_PIXELS
        }
        if (safeJpegSizes.isNotEmpty()) {
            jpegSize = safeJpegSizes.maxByOrNull {
                it.width.toLong() * it.height.toLong()
            } ?: safeJpegSizes.first()
        } else if (jpegSizes.isNotEmpty()) {
            jpegSize = jpegSizes.minByOrNull {
                it.width.toLong() * it.height.toLong()
            } ?: jpegSizes.first()
        }

        val rawSizes = map?.getOutputSizes(ImageFormat.RAW_SENSOR)?.toList().orEmpty()
        val safeRawSizes = rawSizes.filter {
            it.width.toLong() * it.height.toLong() <= MAX_RAW_PIXELS
        }
        if (safeRawSizes.isNotEmpty()) {
            val wantedArea = jpegSize.width.toLong() * jpegSize.height.toLong()
            rawSize = safeRawSizes.minByOrNull {
                abs(it.width.toLong() * it.height.toLong() - wantedArea)
            } ?: safeRawSizes.first()
        } else {
            // A single 200 MP RAW allocation would be too costly for this lightweight app.
            // Prefer an honest JPEG-only fallback to risking an out-of-memory failure.
            rawAdvertised = false
            rawSize = jpegSize
        }
    }

    private fun prepareReaders() {
        jpegReader?.close()
        rawReader?.close()

        jpegReader = ImageReader.newInstance(
            jpegSize.width, jpegSize.height, ImageFormat.JPEG, 2
        ).also { reader ->
            reader.setOnImageAvailableListener({ source ->
                val image = try {
                    source.acquireNextImage()
                } catch (_: Exception) {
                    null
                } ?: return@setOnImageAvailableListener
                synchronized(pendingLock) {
                    pendingJpeg?.close()
                    pendingJpeg = image
                    finishPendingCapture()
                }
            }, cameraHandler)
        }

        rawReader = if (rawAdvertised) {
            ImageReader.newInstance(
                rawSize.width, rawSize.height, ImageFormat.RAW_SENSOR, 1
            ).also { reader ->
                reader.setOnImageAvailableListener({ source ->
                    val image = try {
                        source.acquireNextImage()
                    } catch (_: Exception) {
                        null
                    } ?: return@setOnImageAvailableListener
                    synchronized(pendingLock) {
                        pendingRaw?.close()
                        pendingRaw = image
                        finishPendingCapture()
                    }
                }, cameraHandler)
            }
        } else {
            null
        }
    }

    private fun configurePreviewSession(includeRaw: Boolean) {
        val device = cameraDevice ?: return
        try {
            captureSession?.close()
        } catch (_: Exception) {
        }
        captureSession = null
        val texture = previewView.surfaceTexture ?: return
        try {
            texture.setDefaultBufferSize(previewSize.width, previewSize.height)
            configureTransform(previewView.width, previewView.height)
            previewSurface?.release()
            previewSurface = Surface(texture)

            val outputs = mutableListOf<Surface>()
            outputs.add(previewSurface!!)
            jpegReader?.surface?.let { outputs.add(it) }
            if (includeRaw) rawReader?.surface?.let { outputs.add(it) }

            device.createCaptureSession(
                outputs,
                object : CameraCaptureSession.StateCallback() {
                    override fun onConfigured(session: CameraCaptureSession) {
                        captureSession = session
                        rawSessionActive = includeRaw && rawReader != null
                        try {
                            val builder = device.createCaptureRequest(
                                CameraDevice.TEMPLATE_PREVIEW
                            )
                            builder.addTarget(previewSurface!!)
                            applyControls(builder, still = false)
                            previewBuilder = builder
                            session.setRepeatingRequest(builder.build(), null, cameraHandler)
                            if (rawSessionActive) {
                                listener.onStatus("DNG RAW ready · JPEG pair enabled")
                            } else if (rawAdvertised) {
                                listener.onStatus("Preview ready · RAW stream not available in this session")
                                listener.onCapabilities(currentCapabilities(raw = false))
                            } else {
                                listener.onStatus("Preview ready · JPEG capture")
                            }
                        } catch (error: Exception) {
                            listener.onError("Preview setup failed: " + error.message)
                        }
                    }

                    override fun onConfigureFailed(session: CameraCaptureSession) {
                        if (includeRaw) {
                            rawSessionActive = false
                            rawReader?.close()
                            rawReader = null
                            configurePreviewSession(false)
                        } else {
                            listener.onError("This camera could not start a preview session.")
                        }
                    }
                },
                cameraHandler
            )
        } catch (error: Exception) {
            if (includeRaw) {
                rawSessionActive = false
                rawReader?.close()
                rawReader = null
                configurePreviewSession(false)
            } else {
                listener.onError("Camera session error: " + (error.message ?: "unknown"))
            }
        }
    }

    private fun currentCapabilities(raw: Boolean): CameraCapabilities {
        val chars = characteristics
        val iso = chars?.get(CameraCharacteristics.SENSOR_INFO_SENSITIVITY_RANGE)
            ?: Range(50, 800)
        val exposure = chars?.get(CameraCharacteristics.SENSOR_INFO_EXPOSURE_TIME_RANGE)
            ?: Range(125_000L, 1_000_000_000L)
        val focus = chars?.get(CameraCharacteristics.LENS_INFO_MINIMUM_FOCUS_DISTANCE) ?: 0f
        return CameraCapabilities(
            raw,
            manualSensor,
            iso.lower,
            iso.upper,
            exposure.lower,
            exposure.upper,
            focus
        )
    }

    private fun applyControls(builder: CaptureRequest.Builder, still: Boolean) {
        builder.set(CaptureRequest.CONTROL_MODE, CameraMetadata.CONTROL_MODE_AUTO)

        if (manualExposureEnabled && manualSensor) {
            builder.set(CaptureRequest.CONTROL_AE_MODE, CaptureRequest.CONTROL_AE_MODE_OFF)
            builder.set(CaptureRequest.SENSOR_SENSITIVITY, manualIso)
            builder.set(CaptureRequest.SENSOR_EXPOSURE_TIME, manualExposureNs)
        } else {
            builder.set(CaptureRequest.CONTROL_AE_MODE, CaptureRequest.CONTROL_AE_MODE_ON)
            val aeRange = characteristics?.get(
                CameraCharacteristics.CONTROL_AE_COMPENSATION_RANGE
            )
            if (aeRange != null) {
                builder.set(
                    CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION,
                    exposureCompensation.coerceIn(aeRange.lower, aeRange.upper)
                )
            }
        }

        builder.set(CaptureRequest.CONTROL_AWB_MODE, whiteBalanceMode)
        if (manualFocusDistance != null) {
            builder.set(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_OFF)
            builder.set(CaptureRequest.LENS_FOCUS_DISTANCE, manualFocusDistance!!)
        } else {
            builder.set(
                CaptureRequest.CONTROL_AF_MODE,
                CaptureRequest.CONTROL_AF_MODE_CONTINUOUS_PICTURE
            )
        }

        if (flashEnabled && still) {
            builder.set(CaptureRequest.FLASH_MODE, CaptureRequest.FLASH_MODE_SINGLE)
        } else if (flashEnabled && !still) {
            builder.set(CaptureRequest.FLASH_MODE, CaptureRequest.FLASH_MODE_TORCH)
        } else {
            builder.set(CaptureRequest.FLASH_MODE, CaptureRequest.FLASH_MODE_OFF)
        }

        if (still) builder.set(CaptureRequest.JPEG_QUALITY, 96.toByte())
    }

    private fun updatePreview() {
        val handler = cameraHandler ?: return
        handler.post {
            try {
                val builder = previewBuilder ?: return@post
                val session = captureSession ?: return@post
                applyControls(builder, still = false)
                session.setRepeatingRequest(builder.build(), null, cameraHandler)
            } catch (error: Exception) {
                listener.onError("Could not update camera controls: " + error.message)
            }
        }
    }

    private fun finishPendingCapture() {
        if (!captureInProgress) return
        val jpeg = pendingJpeg ?: return
        val result = pendingResult ?: return
        val raw = if (pendingNeedsRaw) pendingRaw ?: return else pendingRaw

        pendingJpeg = null
        pendingRaw = null
        pendingResult = null
        captureInProgress = false
        val filter = pendingFilter

        saveExecutor.execute {
            saveCapturedPhoto(jpeg, raw, result, filter)
        }
    }

    private fun saveCapturedPhoto(
        jpegImage: Image,
        rawImage: Image?,
        result: TotalCaptureResult,
        filter: FilterPreset
    ) {
        try {
            val jpegBytes = jpegImage.planes[0].buffer.let { buffer ->
                ByteArray(buffer.remaining()).also { buffer.get(it) }
            }
            val rendered = FilterEngine.renderCapture(
                jpegBytes,
                filter,
                desiredOutputAspectRatio(),
                quality = 96
            )
            val stamp = timestamp()

            writeToMediaStore(
                MediaStore.Images.Media.EXTERNAL_CONTENT_URI,
                "GRAIN_" + stamp + "_ORIGINAL.jpg",
                "image/jpeg"
            ) { output ->
                output.write(rendered.originalJpeg)
            }

            val filteredBytes = rendered.filteredJpeg
            if (filteredBytes != null) {
                writeToMediaStore(
                    MediaStore.Images.Media.EXTERNAL_CONTENT_URI,
                    "GRAIN_" + stamp + "_" + filter.fileTag + ".jpg",
                    "image/jpeg"
                ) { output ->
                    output.write(filteredBytes)
                }
            }

            var rawSaved = false
            if (rawImage != null && characteristics != null) {
                try {
                    writeToMediaStore(
                        MediaStore.Images.Media.EXTERNAL_CONTENT_URI,
                        "GRAIN_" + stamp + "_RAW.dng",
                        "image/x-adobe-dng"
                    ) { output ->
                        DngCreator(characteristics!!, result).use { creator ->
                            creator.setOrientation(dngExifOrientation())
                            creator.writeImage(output, rawImage)
                        }
                    }
                    rawSaved = true
                } catch (error: Exception) {
                    listener.onStatus("JPEG saved; DNG export failed: " + error.message)
                }
            }

            val description = buildString {
                append("Saved ")
                if (rawSaved) append("DNG RAW + ")
                append("original JPEG")
                if (filteredBytes != null) append(" + " + filter.title + " JPEG")
                append(" · DCIM/Grain Camera")
            }
            listener.onPhotoSaved(description)
        } catch (error: OutOfMemoryError) {
            listener.onError("Not enough memory to render this photo. Try the Full or 4:3 frame.")
        } catch (error: Exception) {
            listener.onError("Could not save photo: " + (error.message ?: "unknown"))
        } finally {
            try {
                jpegImage.close()
            } catch (_: Exception) {
            }
            try {
                rawImage?.close()
            } catch (_: Exception) {
            }
        }
    }

    private fun writeToMediaStore(
        collection: Uri,
        displayName: String,
        mimeType: String,
        writer: (OutputStream) -> Unit
    ): Uri {
        val values = ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME, displayName)
            put(MediaStore.MediaColumns.MIME_TYPE, mimeType)
            put(
                MediaStore.MediaColumns.RELATIVE_PATH,
                Environment.DIRECTORY_DCIM + "/Grain Camera"
            )
            put(MediaStore.MediaColumns.IS_PENDING, 1)
        }

        val uri = activity.contentResolver.insert(collection, values)
            ?: throw IllegalStateException("Android could not create the media file.")

        try {
            activity.contentResolver.openOutputStream(uri)?.use(writer)
                ?: throw IllegalStateException("Android could not open the media file.")
            val ready = ContentValues().apply {
                put(MediaStore.MediaColumns.IS_PENDING, 0)
            }
            activity.contentResolver.update(uri, ready, null, null)
            return uri
        } catch (error: Exception) {
            activity.contentResolver.delete(uri, null, null)
            throw error
        }
    }

    private fun finishPendingObjects() {
        synchronized(pendingLock) {
            pendingJpeg?.close()
            pendingRaw?.close()
            pendingJpeg = null
            pendingRaw = null
            pendingResult = null
            captureInProgress = false
        }
    }

    private fun jpegOrientation(): Int {
        val sensor = characteristics?.get(CameraCharacteristics.SENSOR_ORIENTATION) ?: 90
        val rotation = activity.windowManager.defaultDisplay.rotation
        val degrees = when (rotation) {
            Surface.ROTATION_0 -> 0
            Surface.ROTATION_90 -> 90
            Surface.ROTATION_180 -> 180
            else -> 270
        }
        val isFront = characteristics?.get(CameraCharacteristics.LENS_FACING) ==
            CameraCharacteristics.LENS_FACING_FRONT
        return if (isFront) (sensor + degrees) % 360
        else (sensor - degrees + 360) % 360
    }

    private fun dngExifOrientation(): Int = when (jpegOrientation()) {
        90 -> ExifInterface.ORIENTATION_ROTATE_90
        180 -> ExifInterface.ORIENTATION_ROTATE_180
        270 -> ExifInterface.ORIENTATION_ROTATE_270
        else -> ExifInterface.ORIENTATION_NORMAL
    }

    private fun timestamp(): String =
        SimpleDateFormat("yyyyMMdd_HHmmss_SSS", Locale.US).format(Date())

    private fun closeCameraResources() {
        try {
            captureSession?.close()
        } catch (_: Exception) {
        }
        captureSession = null
        previewBuilder = null

        try {
            cameraDevice?.close()
        } catch (_: Exception) {
        }
        cameraDevice = null

        try {
            previewSurface?.release()
        } catch (_: Exception) {
        }
        previewSurface = null

        try {
            jpegReader?.close()
        } catch (_: Exception) {
        }
        jpegReader = null
        try {
            rawReader?.close()
        } catch (_: Exception) {
        }
        rawReader = null
        rawSessionActive = false
        finishPendingObjects()
    }
}
