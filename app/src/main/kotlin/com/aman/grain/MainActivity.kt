package com.aman.grain

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.provider.MediaStore
import android.view.Gravity
import android.graphics.SurfaceTexture
import android.view.TextureView
import android.view.View
import android.view.WindowManager
import android.widget.FrameLayout
import android.widget.HorizontalScrollView
import android.widget.LinearLayout
import android.widget.SeekBar
import android.widget.TextView
import android.widget.Toast
import java.util.Locale

class MainActivity : Activity(), CameraEngine.Listener {
    private val paper = Color.rgb(240, 237, 227)
    private val panel = Color.rgb(229, 224, 211)
    private val ink = Color.rgb(39, 43, 36)
    private val muted = Color.rgb(112, 113, 99)
    private val amber = Color.rgb(183, 131, 54)
    private val olive = Color.rgb(91, 101, 73)

    private lateinit var preview: TextureView
    private lateinit var previewOverlay: PreviewOverlay
    private lateinit var status: TextView
    private lateinit var rawBadge: TextView
    private lateinit var shutter: FrameLayout
    private lateinit var advancedPanel: LinearLayout
    private lateinit var advancedToggle: TextView
    private lateinit var isoSeek: SeekBar
    private lateinit var exposureSeek: SeekBar
    private lateinit var focusSeek: SeekBar
    private lateinit var isoValue: TextView
    private lateinit var exposureValue: TextView
    private lateinit var focusValue: TextView
    private lateinit var wbButton: TextView
    private lateinit var manualButton: TextView
    private lateinit var flashButton: TextView
    private lateinit var modePhoto: TextView
    private lateinit var modeVideo: TextView

    private var cameraEngine: CameraEngine? = null
    private var capabilities: CameraCapabilities? = null
    private var selectedFilter = FilterPreset.ORIGINAL
    private var selectedAspect = "4:3"
    private var videoMode = false
    private var recording = false
    private var manualMode = false
    private var flashOn = false
    private var whiteBalance = 0
    private val whiteBalanceModes = listOf("Auto", "Daylight", "Cloudy", "Tungsten", "Fluorescent")
    private var pendingVideoStart = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        window.statusBarColor = paper
        window.navigationBarColor = paper
        window.decorView.systemUiVisibility =
            View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR or View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
        buildInterface()

        preview.surfaceTextureListener = object : TextureView.SurfaceTextureListener {
            override fun onSurfaceTextureAvailable(surface: SurfaceTexture, width: Int, height: Int) {
                startCameraIfAllowed()
            }
            override fun onSurfaceTextureSizeChanged(surface: SurfaceTexture, width: Int, height: Int) {
                cameraEngine?.configureTransform(width, height)
                previewOverlay.invalidate()
            }
            override fun onSurfaceTextureDestroyed(surface: SurfaceTexture): Boolean = true
            override fun onSurfaceTextureUpdated(surface: SurfaceTexture) = Unit
        }

        if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.CAMERA), REQUEST_CAMERA)
        } else {
            startCameraIfAllowed()
        }
    }

    override fun onResume() {
        super.onResume()
        if (::preview.isInitialized && preview.isAvailable) startCameraIfAllowed()
    }

    override fun onPause() {
        cameraEngine?.stop()
        cameraEngine = null
        super.onPause()
    }

    private fun startCameraIfAllowed() {
        if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) return
        if (!preview.isAvailable) return
        if (cameraEngine == null) cameraEngine = CameraEngine(this, preview, this)
        cameraEngine?.start()
    }

    private fun buildInterface() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(paper)
        }

        val header = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(20), dp(8), dp(18), dp(8))
            setBackgroundColor(paper)
        }
        val brandColumn = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_VERTICAL
        }
        val brand = text("GRAIN", 21f, ink, true)
        brand.letterSpacing = 0.16f
        val tagline = text("CAMERA  /  NATURAL LIGHT", 9f, muted, true)
        tagline.letterSpacing = 0.11f
        brandColumn.addView(brand)
        brandColumn.addView(tagline)
        header.addView(brandColumn, LinearLayout.LayoutParams(0, dp(48), 1f))

        advancedToggle = text("CONTROLS  +", 11f, olive, true).apply {
            gravity = Gravity.CENTER
            setPadding(dp(13), dp(10), dp(13), dp(10))
            background = rounded(panel, dp(18))
            setOnClickListener { toggleAdvanced() }
        }
        header.addView(advancedToggle)
        root.addView(header, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, dp(62)
        ))

        val stage = FrameLayout(this).apply { setBackgroundColor(Color.rgb(31, 34, 29)) }
        preview = TextureView(this).apply {
            isOpaque = true
        }
        stage.addView(preview, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT
        ))

        previewOverlay = PreviewOverlay(this)
        stage.addView(previewOverlay, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT
        ))

        stage.setOnTouchListener { _, event ->
            if (event.action == android.view.MotionEvent.ACTION_UP) {
                status.text = "Preview framing · tap the focus controls below"
            }
            true
        }

        val previewLabel = text("GRAIN  •  LIVE VIEW", 10f, Color.WHITE, true).apply {
            setPadding(dp(12), dp(8), dp(12), dp(8))
            background = rounded(Color.argb(180, 30, 34, 29), dp(18))
        }
        stage.addView(previewLabel, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.WRAP_CONTENT, FrameLayout.LayoutParams.WRAP_CONTENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            setMargins(dp(14), dp(14), 0, 0)
        })

        rawBadge = text("CHECKING CAMERA", 9f, Color.WHITE, true).apply {
            gravity = Gravity.CENTER
            setPadding(dp(11), dp(8), dp(11), dp(8))
            background = rounded(Color.argb(180, 30, 34, 29), dp(18))
        }
        stage.addView(rawBadge, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.WRAP_CONTENT, FrameLayout.LayoutParams.WRAP_CONTENT
        ).apply {
            gravity = Gravity.TOP or Gravity.END
            setMargins(0, dp(14), dp(14), 0)
        })

        val centerMark = text("＋", 25f, Color.argb(145, 255, 255, 255), false).apply {
            gravity = Gravity.CENTER
        }
        stage.addView(centerMark, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.WRAP_CONTENT, FrameLayout.LayoutParams.WRAP_CONTENT,
            Gravity.CENTER
        ))
        root.addView(stage, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f
        ))

        val bottom = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(10), dp(16), dp(10))
            setBackgroundColor(paper)
        }

        val filterTitle = text("LOOKS", 9f, muted, true).apply {
            letterSpacing = 0.16f
        }
        bottom.addView(filterTitle, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, dp(18)
        ))

        val filterScroll = HorizontalScrollView(this).apply {
            isHorizontalScrollBarEnabled = false
        }
        val filterRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        FilterPreset.values().forEach { preset ->
            val chip = text(preset.title, 11f, ink, true).apply {
                gravity = Gravity.CENTER
                setPadding(dp(14), dp(9), dp(14), dp(9))
                setOnClickListener {
                    selectedFilter = preset
                    previewOverlay.setLook(preset)
                    refreshFilterChips(filterRow)
                    status.text = if (preset == FilterPreset.ORIGINAL) {
                        "Original look · unfiltered JPEG + DNG"
                    } else {
                        preset.title + " · original JPEG + filtered JPEG + untouched DNG"
                    }
                }
                tag = preset
            }
            filterRow.addView(chip, LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, dp(38)
            ).apply { marginEnd = dp(7) })
        }
        filterScroll.addView(filterRow)
        bottom.addView(filterScroll, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, dp(46)
        ))

        val ratioHeader = text("FRAME", 9f, muted, true).apply {
            letterSpacing = 0.16f
            setPadding(0, dp(3), 0, 0)
        }
        bottom.addView(ratioHeader, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, dp(18)
        ))
        val ratioScroll = HorizontalScrollView(this).apply {
            isHorizontalScrollBarEnabled = false
        }
        val ratioRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        listOf("4:3", "16:9", "1:1", "FULL").forEach { ratio ->
            val chip = text(ratio, 10f, ink, true).apply {
                gravity = Gravity.CENTER
                setPadding(dp(15), dp(7), dp(15), dp(7))
                tag = ratio
                setOnClickListener {
                    selectedAspect = ratio
                    applyAspectRatio()
                    refreshAspectChips(ratioRow)
                }
            }
            ratioRow.addView(chip, LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, dp(34)
            ).apply { marginEnd = dp(7) })
        }
        ratioScroll.addView(ratioRow)
        bottom.addView(ratioScroll, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, dp(39)
        ))

        advancedPanel = buildAdvancedPanel()
        advancedPanel.visibility = View.GONE
        bottom.addView(advancedPanel, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT
        ))

        val separator = View(this).apply { setBackgroundColor(Color.rgb(213, 207, 192)) }
        bottom.addView(separator, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, dp(1)
        ).apply {
            topMargin = dp(5)
            bottomMargin = dp(8)
        })

        val controls = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }

        flashButton = text("FLASH\nOFF", 9f, ink, true).apply {
            gravity = Gravity.CENTER
            setPadding(dp(10), dp(8), dp(10), dp(8))
            background = rounded(panel, dp(12))
            setOnClickListener {
                flashOn = !flashOn
                cameraEngine?.setFlash(flashOn)
                text = if (flashOn) "FLASH\nON" else "FLASH\nOFF"
            }
        }
        controls.addView(flashButton, LinearLayout.LayoutParams(dp(62), dp(46)))

        val galleryButton = text("GALLERY", 9f, muted, true).apply {
            gravity = Gravity.CENTER
            setOnClickListener { openGallery() }
        }
        controls.addView(galleryButton, LinearLayout.LayoutParams(0, dp(54), 1f))

        shutter = FrameLayout(this).apply {
            background = oval(Color.WHITE, amber, dp(3))
            setOnClickListener { onShutterPressed() }
        }
        val inner = View(this).apply {
            background = oval(amber, amber, 0)
        }
        shutter.addView(inner, FrameLayout.LayoutParams(dp(51), dp(51), Gravity.CENTER))
        controls.addView(shutter, LinearLayout.LayoutParams(dp(70), dp(70)).apply {
            marginStart = dp(5)
            marginEnd = dp(5)
        })

        val flip = text("FLIP", 10f, muted, true).apply {
            gravity = Gravity.CENTER
            setOnClickListener {
                cameraEngine?.flipCamera()
                status.text = "Switching camera…"
            }
        }
        controls.addView(flip, LinearLayout.LayoutParams(0, dp(54), 1f))
        bottom.addView(controls, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, dp(76)
        ))

        val modeRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            setPadding(0, dp(4), 0, 0)
        }
        modePhoto = modeButton("PHOTO", selected = true)
        modeVideo = modeButton("VIDEO", selected = false)
        modePhoto.setOnClickListener { setVideoMode(false) }
        modeVideo.setOnClickListener { setVideoMode(true) }
        modeRow.addView(modePhoto, LinearLayout.LayoutParams(dp(104), dp(34)))
        modeRow.addView(modeVideo, LinearLayout.LayoutParams(dp(104), dp(34)))
        bottom.addView(modeRow)

        status = text("Original JPEG + sensor DNG when supported", 10f, muted, false).apply {
            gravity = Gravity.CENTER
            maxLines = 2
            setPadding(0, dp(7), 0, 0)
        }
        bottom.addView(status, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, dp(32)
        ))

        root.addView(bottom, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT
        ))
        setContentView(root)
        refreshFilterChips(filterRow)
        refreshAspectChips(ratioRow)
        applyAspectRatio()
        previewOverlay.setLook(selectedFilter)
    }

    private fun buildAdvancedPanel(): LinearLayout {
        val panelView = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(12), dp(10), dp(12), dp(8))
            background = rounded(panel, dp(15))
        }

        val titleRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        titleRow.addView(text("MANUAL EXPOSURE", 10f, ink, true),
            LinearLayout.LayoutParams(0, dp(28), 1f))
        manualButton = text("AE AUTO", 9f, olive, true).apply {
            gravity = Gravity.CENTER
            setPadding(dp(10), dp(7), dp(10), dp(7))
            background = rounded(paper, dp(12))
            setOnClickListener {
                manualMode = !manualMode
                cameraEngine?.setManualMode(manualMode)
                text = if (manualMode) "AE MANUAL" else "AE AUTO"
                if (manualMode) applyManualSettings()
                status.text = if (manualMode) "Manual ISO and shutter active" else "Auto exposure active"
            }
        }
        titleRow.addView(manualButton)
        panelView.addView(titleRow)

        isoValue = text("ISO 100", 10f, ink, true)
        panelView.addView(isoValue)
        isoSeek = SeekBar(this).apply {
            max = 100
            progress = 20
            setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
                override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) {
                    val caps = capabilities ?: return
                    val iso = isoAtProgress(progress, caps)
                    isoValue.text = "ISO " + iso
                    if (fromUser) applyManualSettings(iso = iso)
                }
                override fun onStartTrackingTouch(seekBar: SeekBar?) {
                    enableManualExposure()
                }
                override fun onStopTrackingTouch(seekBar: SeekBar?) = Unit
            })
        }
        panelView.addView(isoSeek, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, dp(34)
        ))

        exposureValue = text("SHUTTER  1/100", 10f, ink, true)
        panelView.addView(exposureValue)
        exposureSeek = SeekBar(this).apply {
            max = 100
            progress = 35
            setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
                override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) {
                    val caps = capabilities ?: return
                    val ns = interpolateExposure(progress, caps)
                    exposureValue.text = "SHUTTER  " + formatShutter(ns)
                    if (fromUser) applyManualSettings(exposure = ns)
                }
                override fun onStartTrackingTouch(seekBar: SeekBar?) {
                    enableManualExposure()
                }
                override fun onStopTrackingTouch(seekBar: SeekBar?) = Unit
            })
        }
        panelView.addView(exposureSeek, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, dp(34)
        ))

        val focusRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        focusValue = text("FOCUS  AUTO", 10f, ink, true)
        focusRow.addView(focusValue, LinearLayout.LayoutParams(0, dp(28), 1f))
        wbButton = text("WB  AUTO", 9f, olive, true).apply {
            gravity = Gravity.CENTER
            setPadding(dp(10), dp(7), dp(10), dp(7))
            background = rounded(paper, dp(12))
            setOnClickListener {
                whiteBalance = (whiteBalance + 1) % whiteBalanceModes.size
                val name = whiteBalanceModes[whiteBalance]
                text = "WB  " + name.uppercase()
                cameraEngine?.setWhiteBalance(name)
            }
        }
        focusRow.addView(wbButton)
        panelView.addView(focusRow)

        focusSeek = SeekBar(this).apply {
            max = 100
            progress = 0
            setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
                override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) {
                    val maxFocus = capabilities?.minFocusDistance ?: 0f
                    if (maxFocus <= 0f) return
                    val distance = maxFocus * progress / 100f
                    focusValue.text = "FOCUS  " + String.format(Locale.US, "%.1f", distance) + " D"
                    if (fromUser) cameraEngine?.setManualFocus(distance)
                }
                override fun onStartTrackingTouch(seekBar: SeekBar?) = Unit
                override fun onStopTrackingTouch(seekBar: SeekBar?) = Unit
            })
        }
        panelView.addView(focusSeek, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, dp(34)
        ))

        val note = text(
            "DNG is saved untouched. Selected looks affect a separate JPEG copy.",
            9f, muted, false
        )
        panelView.addView(note, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT
        ).apply { topMargin = dp(3) })

        return panelView
    }

    private fun applyManualSettings(iso: Int? = null, exposure: Long? = null) {
        val caps = capabilities ?: return
        val currentIso = iso ?: run {
            val p = isoSeek.progress
            caps.minIso + ((caps.maxIso - caps.minIso).toDouble() * p / 100.0).toInt()
        }
        val currentExposure = exposure ?: interpolateExposure(exposureSeek.progress, caps)
        cameraEngine?.setManualExposure(currentIso, currentExposure)
    }

    private fun enableManualExposure() {
        manualMode = true
        manualButton.text = "AE MANUAL"
        cameraEngine?.setManualMode(true)
    }

    private fun interpolateExposure(progress: Int, caps: CameraCapabilities): Long {
        val min = caps.minExposureNs.coerceAtLeast(125_000L).toDouble()
        val max = caps.maxExposureNs.coerceAtMost(1_000_000_000L).toDouble()
        val fraction = progress.coerceIn(0, 100) / 100.0
        return (min * Math.pow(max / min, fraction)).toLong()
    }

    private fun formatShutter(ns: Long): String {
        if (ns <= 0L) return "AUTO"
        val denominator = (1_000_000_000.0 / ns).toInt()
        return if (denominator >= 2) "1/" + denominator
        else String.format(Locale.US, "%.2f ms", ns / 1_000_000.0)
    }

    private fun isoAtProgress(progress: Int, caps: CameraCapabilities): Int {
        val min = caps.minIso.coerceAtLeast(1).toDouble()
        val max = caps.maxIso.coerceAtLeast(caps.minIso).toDouble()
        val fraction = progress.coerceIn(0, 100) / 100.0
        return (min * Math.pow(max / min, fraction)).toInt().coerceIn(
            caps.minIso, caps.maxIso
        )
    }

    private fun progressForIso(value: Int, caps: CameraCapabilities): Int {
        val min = caps.minIso.coerceAtLeast(1).toDouble()
        val max = caps.maxIso.coerceAtLeast(caps.minIso).toDouble()
        if (max <= min) return 0
        return (Math.log(value.coerceIn(caps.minIso, caps.maxIso) / min) /
            Math.log(max / min) * 100.0).toInt().coerceIn(0, 100)
    }

    private fun progressForExposure(value: Long, caps: CameraCapabilities): Int {
        val min = caps.minExposureNs.coerceAtLeast(125_000L).toDouble()
        val max = caps.maxExposureNs.coerceAtMost(1_000_000_000L).toDouble()
        if (max <= min) return 0
        return (Math.log(value.coerceIn(min.toLong(), max.toLong()) / min) /
            Math.log(max / min) * 100.0).toInt().coerceIn(0, 100)
    }

    private fun aspectValue(): Float = when (selectedAspect) {
        "4:3" -> 4f / 3f
        "16:9" -> 16f / 9f
        "1:1" -> 1f
        else -> 0f
    }

    private fun applyAspectRatio() {
        cameraEngine?.setAspectRatio(aspectValue())
        if (::previewOverlay.isInitialized) previewOverlay.setAspect(aspectValue())
        status.text = if (selectedAspect == "FULL") {
            "Full sensor frame selected"
        } else {
            selectedAspect + " frame · original and filtered JPEGs use this crop"
        }
    }

    private fun refreshAspectChips(row: LinearLayout) {
        for (index in 0 until row.childCount) {
            val chip = row.getChildAt(index) as? TextView ?: continue
            val ratio = chip.tag as? String ?: continue
            val selected = ratio == selectedAspect
            chip.setTextColor(if (selected) Color.WHITE else ink)
            chip.background = rounded(if (selected) olive else panel, dp(16))
        }
    }

    private fun refreshFilterChips(row: LinearLayout) {
        for (index in 0 until row.childCount) {
            val chip = row.getChildAt(index) as? TextView ?: continue
            val preset = chip.tag as? FilterPreset ?: continue
            val selected = preset == selectedFilter
            chip.setTextColor(if (selected) Color.WHITE else ink)
            chip.background = rounded(if (selected) olive else panel, dp(18))
        }
    }

    private fun setVideoMode(enabled: Boolean) {
        videoMode = enabled
        modePhoto.background = rounded(if (!enabled) olive else panel, dp(18))
        modeVideo.background = rounded(if (enabled) olive else panel, dp(18))
        modePhoto.setTextColor(if (!enabled) Color.WHITE else ink)
        modeVideo.setTextColor(if (enabled) Color.WHITE else ink)
        flashButton.visibility = if (enabled) View.INVISIBLE else View.VISIBLE
        status.text = if (enabled) {
            "Standard MP4 video · no AI looks · mic permission optional"
        } else {
            "Still photo · DNG RAW + original JPEG when supported"
        }
    }

    private fun onShutterPressed() {
        val engine = cameraEngine ?: return
        if (videoMode) {
            if (recording) {
                engine.stopVideo()
            } else if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) ==
                PackageManager.PERMISSION_GRANTED
            ) {
                engine.startVideo(withAudio = true)
            } else {
                pendingVideoStart = true
                requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), REQUEST_AUDIO)
            }
        } else {
            engine.takePhoto(selectedFilter)
        }
    }

    private fun toggleAdvanced() {
        val visible = advancedPanel.visibility == View.VISIBLE
        advancedPanel.visibility = if (visible) View.GONE else View.VISIBLE
        advancedToggle.text = if (visible) "CONTROLS  +" else "CONTROLS  −"
    }

    private fun openGallery() {
        try {
            val intent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, "image/*")
            }
            startActivity(intent)
        } catch (_: Exception) {
            Toast.makeText(this, "No gallery app is available.", Toast.LENGTH_SHORT).show()
        }
    }

    private fun modeButton(label: String, selected: Boolean): TextView =
        text(label, 10f, if (selected) Color.WHITE else ink, true).apply {
            gravity = Gravity.CENTER
            background = rounded(if (selected) olive else panel, dp(18))
        }

    private fun text(
        value: String,
        size: Float,
        color: Int,
        bold: Boolean
    ): TextView = TextView(this).apply {
        text = value
        textSize = size
        setTextColor(color)
        if (bold) setTypeface(typeface, android.graphics.Typeface.BOLD)
        includeFontPadding = false
    }

    private fun rounded(color: Int, radius: Int): GradientDrawable =
        GradientDrawable().apply {
            setColor(color)
            cornerRadius = radius.toFloat()
        }

    private fun oval(fill: Int, stroke: Int, strokeWidth: Int): GradientDrawable =
        GradientDrawable().apply {
            shape = GradientDrawable.OVAL
            setColor(fill)
            if (strokeWidth > 0) setStroke(dp(strokeWidth), stroke)
        }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    override fun onStatus(message: String) {
        runOnUiThread { status.text = message }
    }

    override fun onCapabilities(capabilities: CameraCapabilities) {
        this.capabilities = capabilities
        runOnUiThread {
            rawBadge.text = if (capabilities.raw) "DNG RAW  ·  READY" else "JPEG  ·  RAW UNAVAILABLE"
            rawBadge.background = rounded(
                Color.argb(190, 30, 34, 29), dp(18)
            )
            status.text = if (capabilities.manualSensor) "MANUAL ISO / SHUTTER READY"
                else "MANUAL SENSOR CONTROLS UNAVAILABLE"
            isoSeek.isEnabled = capabilities.manualSensor
            exposureSeek.isEnabled = capabilities.manualSensor
            if (capabilities.manualSensor) {
                isoSeek.progress = progressForIso(100.coerceIn(
                    capabilities.minIso, capabilities.maxIso
                ), capabilities)
                exposureSeek.progress = progressForExposure(
                    10_000_000L.coerceIn(
                        capabilities.minExposureNs,
                        capabilities.maxExposureNs
                    ),
                    capabilities
                )
                isoValue.text = "ISO " + isoAtProgress(isoSeek.progress, capabilities)
                exposureValue.text = "SHUTTER  " + formatShutter(
                    interpolateExposure(exposureSeek.progress, capabilities)
                )
            }
            focusSeek.isEnabled = capabilities.minFocusDistance > 0f
            if (capabilities.minFocusDistance <= 0f) focusValue.text = "FOCUS  AUTO"
        }
    }

    override fun onPhotoSaved(message: String) {
        runOnUiThread { status.text = message }
    }

    override fun onRecordingChanged(recording: Boolean) {
        this.recording = recording
        runOnUiThread {
            shutter.background = oval(
                if (recording) Color.rgb(183, 75, 59) else Color.WHITE,
                amber,
                3
            )
            val inner = shutter.getChildAt(0)
            inner?.background = if (recording) rounded(Color.WHITE, dp(5))
                else oval(amber, amber, 0)
            status.text = if (recording) "RECORDING  ·  TAP TO STOP"
                else "Video saved to DCIM/Grain Camera"
        }
    }

    override fun onError(message: String) {
        runOnUiThread {
            status.text = message
            Toast.makeText(this, message, Toast.LENGTH_LONG).show()
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQUEST_CAMERA) {
            if (grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED) {
                startCameraIfAllowed()
            } else {
                status.text = "Camera permission is needed to take photos."
            }
        } else if (requestCode == REQUEST_AUDIO) {
            if (pendingVideoStart) {
                pendingVideoStart = false
                cameraEngine?.startVideo(
                    withAudio = grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED
                )
                if (grantResults.firstOrNull() != PackageManager.PERMISSION_GRANTED) {
                    status.text = "Recording video without microphone audio."
                }
            }
        }
    }


    private inner class PreviewOverlay(context: android.content.Context) : View(context) {
        private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
        private var look = FilterPreset.ORIGINAL
        private var aspect = 4f / 3f

        init {
            isClickable = false
            isFocusable = false
        }

        fun setLook(value: FilterPreset) {
            look = value
            invalidate()
        }

        fun setAspect(value: Float) {
            aspect = value
            invalidate()
        }

        override fun onDraw(canvas: android.graphics.Canvas) {
            super.onDraw(canvas)
            val viewWidth = width.toFloat()
            val viewHeight = height.toFloat()
            if (viewWidth <= 0f || viewHeight <= 0f) return

            val frame = if (aspect <= 0f) {
                RectF(0f, 0f, viewWidth, viewHeight)
            } else {
                val frameAspect = if (viewWidth >= viewHeight) aspect else 1f / aspect
                val viewAspect = viewWidth / viewHeight
                if (viewAspect > frameAspect) {
                    val frameWidth = viewHeight * frameAspect
                    val left = (viewWidth - frameWidth) / 2f
                    RectF(left, 0f, left + frameWidth, viewHeight)
                } else {
                    val frameHeight = viewWidth / frameAspect
                    val top = (viewHeight - frameHeight) / 2f
                    RectF(0f, top, viewWidth, top + frameHeight)
                }
            }

            val tint = when (look) {
                FilterPreset.ORIGINAL -> Color.TRANSPARENT
                FilterPreset.GOLDEN_HOUR -> Color.argb(24, 255, 169, 74)
                FilterPreset.SOFT_FILM -> Color.argb(20, 218, 181, 137)
                FilterPreset.CINEMATIC -> Color.argb(18, 33, 49, 65)
                FilterPreset.COOL_FADE -> Color.argb(26, 91, 151, 194)
                FilterPreset.MONO -> Color.argb(25, 185, 185, 185)
            }
            if (tint != Color.TRANSPARENT) {
                paint.color = tint
                canvas.drawRect(frame, paint)
            }

            if (aspect > 0f) {
                val outside = Path().apply {
                    fillType = Path.FillType.EVEN_ODD
                    addRect(RectF(0f, 0f, viewWidth, viewHeight), Path.Direction.CW)
                    addRect(frame, Path.Direction.CCW)
                }
                paint.color = Color.argb(126, 0, 0, 0)
                canvas.drawPath(outside, paint)
                paint.color = Color.argb(220, 255, 255, 255)
                paint.style = Paint.Style.STROKE
                paint.strokeWidth = dp(1).toFloat()
                canvas.drawRect(frame, paint)
                paint.style = Paint.Style.FILL
            }
        }
    }

    companion object {
        private const val REQUEST_CAMERA = 100
        private const val REQUEST_AUDIO = 101
    }
}
