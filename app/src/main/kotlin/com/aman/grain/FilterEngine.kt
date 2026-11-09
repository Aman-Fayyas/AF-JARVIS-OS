package com.aman.grain

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.media.ExifInterface
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import kotlin.math.roundToInt

enum class FilterPreset(val title: String, val fileTag: String) {
    ORIGINAL("Original", "original"),
    GOLDEN_HOUR("Golden hour", "golden-hour"),
    SOFT_FILM("Soft film", "soft-film"),
    CINEMATIC("Cinematic", "cinematic"),
    COOL_FADE("Cool fade", "cool-fade"),
    MONO("Mono", "mono")
}

data class RenderedCapture(
    val originalJpeg: ByteArray,
    val filteredJpeg: ByteArray?
)

/**
 * Creates a correctly oriented, aspect-cropped original JPEG and an optional
 * filtered JPEG. The camera DNG never enters this code path.
 *
 * Pixel processing is done in small horizontal strips. This avoids holding both
 * a 12 MP source bitmap and a second 12 MP output bitmap in memory on the S9+.
 */
object FilterEngine {
    fun renderCapture(
        jpeg: ByteArray,
        preset: FilterPreset,
        desiredAspectRatio: Float = 0f,
        quality: Int = 96
    ): RenderedCapture {
        val orientation = readOrientation(jpeg)
        val needsRotation = orientation != ExifInterface.ORIENTATION_NORMAL &&
            orientation != ExifInterface.ORIENTATION_UNDEFINED
        val source = BitmapFactory.decodeByteArray(jpeg, 0, jpeg.size)
            ?: return RenderedCapture(jpeg, null)

        var working = source
        if (needsRotation) {
            val matrix = Matrix()
            when (orientation) {
                ExifInterface.ORIENTATION_ROTATE_90 -> matrix.postRotate(90f)
                ExifInterface.ORIENTATION_ROTATE_180 -> matrix.postRotate(180f)
                ExifInterface.ORIENTATION_ROTATE_270 -> matrix.postRotate(270f)
                ExifInterface.ORIENTATION_FLIP_HORIZONTAL -> matrix.preScale(-1f, 1f)
                ExifInterface.ORIENTATION_FLIP_VERTICAL -> matrix.preScale(1f, -1f)
                ExifInterface.ORIENTATION_TRANSPOSE -> {
                    matrix.postRotate(90f)
                    matrix.postScale(-1f, 1f)
                }
                ExifInterface.ORIENTATION_TRANSVERSE -> {
                    matrix.postRotate(270f)
                    matrix.postScale(-1f, 1f)
                }
            }
            working = Bitmap.createBitmap(
                source, 0, 0, source.width, source.height, matrix, true
            )
            if (working !== source) source.recycle()
        }

        val crop = cropToAspect(working, desiredAspectRatio)
        if (crop != null) {
            val cropped = Bitmap.createBitmap(
                working, crop[0], crop[1], crop[2], crop[3]
            )
            if (cropped !== working) working.recycle()
            working = cropped
        }

        val originalNeedsRender = needsRotation || crop != null
        val originalBytes = if (originalNeedsRender) {
            compress(working, quality)
        } else {
            jpeg
        }

        val filteredBytes = if (preset == FilterPreset.ORIGINAL) {
            null
        } else {
            applyPresetInPlace(working, preset)
            compress(working, quality)
        }

        working.recycle()
        return RenderedCapture(originalBytes, filteredBytes)
    }

    private fun readOrientation(jpeg: ByteArray): Int {
        return try {
            ExifInterface(ByteArrayInputStream(jpeg)).getAttributeInt(
                ExifInterface.TAG_ORIENTATION,
                ExifInterface.ORIENTATION_NORMAL
            )
        } catch (_: Exception) {
            ExifInterface.ORIENTATION_NORMAL
        }
    }

    private fun cropToAspect(bitmap: Bitmap, desiredAspectRatio: Float): IntArray? {
        if (desiredAspectRatio <= 0f) return null
        val current = bitmap.width.toFloat() / bitmap.height.toFloat()
        if (kotlin.math.abs(current - desiredAspectRatio) < 0.01f) return null

        return if (current > desiredAspectRatio) {
            val width = (bitmap.height * desiredAspectRatio).roundToInt()
                .coerceIn(1, bitmap.width)
            intArrayOf((bitmap.width - width) / 2, 0, width, bitmap.height)
        } else {
            val height = (bitmap.width / desiredAspectRatio).roundToInt()
                .coerceIn(1, bitmap.height)
            intArrayOf(0, (bitmap.height - height) / 2, bitmap.width, height)
        }
    }

    private fun applyPresetInPlace(bitmap: Bitmap, preset: FilterPreset) {
        val width = bitmap.width
        val height = bitmap.height
        val rowsPerStrip = 24
        val pixels = IntArray(width * rowsPerStrip)

        var top = 0
        while (top < height) {
            val rows = minOf(rowsPerStrip, height - top)
            val count = width * rows
            bitmap.getPixels(pixels, 0, width, 0, top, width, rows)

            for (index in 0 until count) {
                val pixel = pixels[index]
                val alpha = pixel ushr 24
                val red = (pixel shr 16) and 0xff
                val green = (pixel shr 8) and 0xff
                val blue = pixel and 0xff
                val luminance = 0.2126f * red + 0.7152f * green + 0.0722f * blue

                var outRed = red
                var outGreen = green
                var outBlue = blue

                when (preset) {
                    FilterPreset.ORIGINAL -> Unit
                    FilterPreset.GOLDEN_HOUR -> {
                        outRed = tone(red, 1.04f, 17f)
                        outGreen = tone(green, 1.04f, 7f)
                        outBlue = tone(blue, 1.04f, -15f)
                    }
                    FilterPreset.SOFT_FILM -> {
                        outRed = tone(red, 0.91f, 10f)
                        outGreen = tone(green, 0.91f, 7f)
                        outBlue = tone(blue, 0.91f, 4f)
                    }
                    FilterPreset.CINEMATIC -> {
                        val shadowCool = (1f - luminance / 255f).coerceIn(0f, 1f) * 10f
                        val highlightWarm = (luminance / 255f).coerceIn(0f, 1f) * 9f
                        outRed = tone(red, 1.12f, highlightWarm)
                        outGreen = tone(green, 1.12f, 0f)
                        outBlue = tone(blue, 1.12f, shadowCool - 2f)
                    }
                    FilterPreset.COOL_FADE -> {
                        outRed = tone(red, 0.92f, 3f)
                        outGreen = tone(green, 0.92f, 8f)
                        outBlue = tone(blue, 0.92f, 19f)
                    }
                    FilterPreset.MONO -> {
                        val gray = tone(luminance.roundToInt(), 1.06f, 0f)
                        outRed = gray
                        outGreen = gray
                        outBlue = gray
                    }
                }

                pixels[index] = (alpha shl 24) or
                    (outRed shl 16) or (outGreen shl 8) or outBlue
            }

            bitmap.setPixels(pixels, 0, width, 0, top, width, rows)
            top += rows
        }
    }

    private fun tone(value: Int, contrast: Float, offset: Float): Int =
        (((value - 128f) * contrast) + 128f + offset)
            .roundToInt().coerceIn(0, 255)

    private fun tone(value: Float, contrast: Float, offset: Float): Int =
        (((value - 128f) * contrast) + 128f + offset)
            .roundToInt().coerceIn(0, 255)

    private fun compress(bitmap: Bitmap, quality: Int): ByteArray {
        val stream = ByteArrayOutputStream()
        bitmap.compress(
            Bitmap.CompressFormat.JPEG,
            quality.coerceIn(88, 100),
            stream
        )
        return stream.toByteArray()
    }
}
