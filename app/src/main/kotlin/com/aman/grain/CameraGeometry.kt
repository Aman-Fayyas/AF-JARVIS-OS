package com.aman.grain

import kotlin.math.abs
import kotlin.math.roundToInt

/**
 * Pure geometry used for saved-photo framing and orientation math.
 * ViewfinderView handles preview transforms independently.
 */
internal object CameraGeometry {
    fun jpegOrientation(sensorOrientation: Int, displayRotation: Int, frontFacing: Boolean): Int {
        // Display#getRotation is counter-clockwise: back = sensor - display,
        // front = sensor + display. This is the Camera2 JPEG_ORIENTATION convention.
        val rotation = if (frontFacing) sensorOrientation + displayRotation
        else sensorOrientation - displayRotation
        return ((rotation % 360) + 360) % 360
    }

    fun centerCropRect(width: Int, height: Int, targetAspectRatio: Float): IntArray? {
        if (width <= 0 || height <= 0 || targetAspectRatio <= 0f) return null
        val currentAspect = width.toFloat() / height.toFloat()
        if (abs(currentAspect - targetAspectRatio) < 0.002f) return null

        return if (currentAspect > targetAspectRatio) {
            val cropWidth = (height * targetAspectRatio).roundToInt().coerceIn(1, width)
            intArrayOf((width - cropWidth) / 2, 0, cropWidth, height)
        } else {
            val cropHeight = (width / targetAspectRatio).roundToInt().coerceIn(1, height)
            intArrayOf(0, (height - cropHeight) / 2, width, cropHeight)
        }
    }
}
