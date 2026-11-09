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
    PORTRA("Portra", "portra"),
    SOFT_FILM("Soft film", "soft-film"),
    CINEMATIC("Cinematic", "cinematic"),
    COOL_FADE("Cool fade", "cool-fade"),
    MONO("Mono", "mono"),
    VIVID("Vivid", "vivid"),
    TEAL_ORANGE("Teal & orange", "teal-orange"),
    VINTAGE("Vintage", "vintage"),
    AUTUMN("Autumn", "autumn"),
    ARCTIC("Arctic", "arctic"),
    NOIR("Noir", "noir"),
    MATTE("Matte", "matte"),
    CLEAN("Clean", "clean")
}

data class RenderedCapture(
    val originalJpeg: ByteArray,
    val filteredJpeg: ByteArray?
)

/**
 * Produces an upright, aspect-framed JPEG pair. Sensor DNG data never enters
 * this renderer, so RAW remains an untouched sensor capture.
 *
 * Pixel processing uses narrow strips to avoid allocating a second full-size
 * bitmap on memory-constrained phones such as the Galaxy S9+.
 */
object FilterEngine {
    fun renderCapture(
        jpeg: ByteArray,
        preset: FilterPreset,
        desiredAspectRatio: Float = 0f,
        quality: Int = 98
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

        val crop = CameraGeometry.centerCropRect(
            working.width,
            working.height,
            desiredAspectRatio
        )
        if (crop != null) {
            val cropped = Bitmap.createBitmap(working, crop[0], crop[1], crop[2], crop[3])
            if (cropped !== working) working.recycle()
            working = cropped
        }

        val originalNeedsRender = needsRotation || crop != null
        val originalBytes = if (originalNeedsRender) compress(working, quality) else jpeg
        val filteredBytes = if (preset == FilterPreset.ORIGINAL) {
            null
        } else {
            applyPresetInPlace(working, preset)
            compress(working, quality)
        }

        working.recycle()
        return RenderedCapture(originalBytes, filteredBytes)
    }

    private fun readOrientation(jpeg: ByteArray): Int =
        try {
            ExifInterface(ByteArrayInputStream(jpeg)).getAttributeInt(
                ExifInterface.TAG_ORIENTATION,
                ExifInterface.ORIENTATION_NORMAL
            )
        } catch (_: Exception) {
            ExifInterface.ORIENTATION_NORMAL
        }

    private fun applyPresetInPlace(bitmap: Bitmap, preset: FilterPreset) {
        val width = bitmap.width
        val height = bitmap.height
        val rowsPerStrip = 20
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
                val luma = 0.2126f * red + 0.7152f * green + 0.0722f * blue
                val shadow = (1f - luma / 255f).coerceIn(0f, 1f)
                val highlight = (luma / 255f).coerceIn(0f, 1f)

                val outRed: Int
                val outGreen: Int
                val outBlue: Int

                when (preset) {
                    FilterPreset.ORIGINAL -> {
                        outRed = red
                        outGreen = green
                        outBlue = blue
                    }
                    FilterPreset.GOLDEN_HOUR -> {
                        outRed = grade(red, luma, 1.08f, 1.06f, 18f + highlight * 4f)
                        outGreen = grade(green, luma, 1.02f, 1.02f, 6f)
                        outBlue = tone(blue, 1.02f, -19f - highlight * 3f)
                    }
                    FilterPreset.PORTRA -> {
                        outRed = grade(red, luma, 0.91f, 0.94f, 13f)
                        outGreen = grade(green, luma, 0.88f, 0.94f, 8f)
                        outBlue = grade(blue, luma, 0.84f, 0.96f, 2f)
                    }
                    FilterPreset.SOFT_FILM -> {
                        outRed = grade(red, luma, 0.88f, 0.88f, 15f)
                        outGreen = grade(green, luma, 0.86f, 0.90f, 11f)
                        outBlue = grade(blue, luma, 0.88f, 0.91f, 8f)
                    }
                    FilterPreset.CINEMATIC -> {
                        val warm = highlight * 12f
                        val cool = shadow * 11f
                        outRed = tone(red, 1.19f, warm + 2f)
                        outGreen = tone(green, 1.16f, -1f)
                        outBlue = tone(blue, 1.19f, cool - 5f)
                    }
                    FilterPreset.COOL_FADE -> {
                        outRed = grade(red, luma, 0.88f, 0.91f, 4f)
                        outGreen = grade(green, luma, 0.92f, 0.92f, 10f)
                        outBlue = grade(blue, luma, 1.03f, 0.93f, 24f)
                    }
                    FilterPreset.MONO -> {
                        val gray = tone(luma, 1.13f, 0f)
                        outRed = gray
                        outGreen = gray
                        outBlue = gray
                    }
                    FilterPreset.VIVID -> {
                        outRed = grade(red, luma, 1.34f, 1.08f, 0f)
                        outGreen = grade(green, luma, 1.34f, 1.08f, 0f)
                        outBlue = grade(blue, luma, 1.34f, 1.08f, 0f)
                    }
                    FilterPreset.TEAL_ORANGE -> {
                        outRed = tone(red, 1.17f, highlight * 16f - shadow * 2f)
                        outGreen = tone(green, 1.13f, shadow * 8f - highlight * 2f)
                        outBlue = tone(blue, 1.16f, shadow * 15f - highlight * 7f)
                    }
                    FilterPreset.VINTAGE -> {
                        outRed = grade(red, luma, 0.82f, 0.86f, 20f)
                        outGreen = grade(green, luma, 0.82f, 0.88f, 13f)
                        outBlue = grade(blue, luma, 0.78f, 0.90f, 4f)
                    }
                    FilterPreset.AUTUMN -> {
                        outRed = grade(red, luma, 1.14f, 1.08f, 15f)
                        outGreen = tone(green, 1.04f, 4f - highlight * 5f)
                        outBlue = tone(blue, 1.06f, -20f)
                    }
                    FilterPreset.ARCTIC -> {
                        outRed = tone(red, 1.06f, -8f)
                        outGreen = grade(green, luma, 1.04f, 1.03f, 7f)
                        outBlue = grade(blue, luma, 1.12f, 1.06f, 18f)
                    }
                    FilterPreset.NOIR -> {
                        val gray = tone(luma, 1.42f, -4f)
                        outRed = gray
                        outGreen = gray
                        outBlue = gray
                    }
                    FilterPreset.MATTE -> {
                        outRed = grade(red, luma, 0.90f, 0.82f, 22f)
                        outGreen = grade(green, luma, 0.88f, 0.84f, 19f)
                        outBlue = grade(blue, luma, 0.88f, 0.86f, 16f)
                    }
                    FilterPreset.CLEAN -> {
                        outRed = grade(red, luma, 1.08f, 1.07f, 1f)
                        outGreen = grade(green, luma, 1.08f, 1.07f, 1f)
                        outBlue = grade(blue, luma, 1.08f, 1.07f, 1f)
                    }
                }

                pixels[index] = (alpha shl 24) or
                    (outRed shl 16) or (outGreen shl 8) or outBlue
            }

            bitmap.setPixels(pixels, 0, width, 0, top, width, rows)
            top += rows
        }
    }

    private fun grade(
        channel: Int,
        luma: Float,
        saturation: Float,
        contrast: Float,
        offset: Float
    ): Int = tone(luma + (channel - luma) * saturation, contrast, offset)

    private fun tone(value: Int, contrast: Float, offset: Float): Int =
        tone(value.toFloat(), contrast, offset)

    private fun tone(value: Float, contrast: Float, offset: Float): Int =
        (((value - 128f) * contrast) + 128f + offset).roundToInt().coerceIn(0, 255)

    private fun compress(bitmap: Bitmap, quality: Int): ByteArray {
        val stream = ByteArrayOutputStream()
        bitmap.compress(Bitmap.CompressFormat.JPEG, quality.coerceIn(92, 100), stream)
        return stream.toByteArray()
    }
}
