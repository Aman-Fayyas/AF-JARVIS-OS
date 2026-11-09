package com.aman.grain

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.ColorMatrix
import android.graphics.ColorMatrixColorFilter
import android.graphics.Paint
import java.io.ByteArrayOutputStream

enum class FilterPreset(val title: String, val fileTag: String) {
    ORIGINAL("Original", "original"),
    GOLDEN_HOUR("Golden hour", "golden-hour"),
    SOFT_FILM("Soft film", "soft-film"),
    CINEMATIC("Cinematic", "cinematic"),
    COOL_FADE("Cool fade", "cool-fade"),
    MONO("Mono", "mono")
}

/**
 * Filters are applied to a JPEG copy after capture. The sensor DNG is never passed
 * through this class, so the RAW file stays untouched.
 */
object FilterEngine {
    fun applyToJpeg(jpeg: ByteArray, preset: FilterPreset, quality: Int = 95): ByteArray {
        if (preset == FilterPreset.ORIGINAL) return jpeg

        val source = BitmapFactory.decodeByteArray(jpeg, 0, jpeg.size)
            ?: return jpeg

        val output = Bitmap.createBitmap(source.width, source.height, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(output)
        val paint = Paint(Paint.FILTER_BITMAP_FLAG or Paint.DITHER_FLAG)
        paint.colorFilter = ColorMatrixColorFilter(matrixFor(preset))
        canvas.drawBitmap(source, 0f, 0f, paint)

        val stream = ByteArrayOutputStream()
        output.compress(Bitmap.CompressFormat.JPEG, quality.coerceIn(80, 100), stream)
        val bytes = stream.toByteArray()

        output.recycle()
        source.recycle()
        return bytes
    }

    private fun matrixFor(preset: FilterPreset): ColorMatrix {
        val saturation = when (preset) {
            FilterPreset.ORIGINAL -> 1.0f
            FilterPreset.GOLDEN_HOUR -> 1.08f
            FilterPreset.SOFT_FILM -> 0.88f
            FilterPreset.CINEMATIC -> 0.94f
            FilterPreset.COOL_FADE -> 0.92f
            FilterPreset.MONO -> 0.0f
        }

        val tone = when (preset) {
            FilterPreset.GOLDEN_HOUR -> floatArrayOf(
                1.07f, 0.025f, 0f, 0f, 5f,
                0.015f, 1.025f, 0f, 0f, 2f,
                0f, 0.005f, 0.91f, 0f, -5f,
                0f, 0f, 0f, 1f, 0f
            )
            FilterPreset.SOFT_FILM -> floatArrayOf(
                0.94f, 0.02f, 0f, 0f, 7f,
                0.015f, 0.94f, 0f, 0f, 6f,
                0f, 0.015f, 0.91f, 0f, 5f,
                0f, 0f, 0f, 1f, 0f
            )
            FilterPreset.CINEMATIC -> floatArrayOf(
                1.05f, 0f, 0f, 0f, 2f,
                0f, 1.00f, 0f, 0f, 0f,
                0f, 0.015f, 0.96f, 0f, 2f,
                0f, 0f, 0f, 1f, 0f
            )
            FilterPreset.COOL_FADE -> floatArrayOf(
                0.94f, 0f, 0.01f, 0f, 7f,
                0f, 0.98f, 0.015f, 0f, 7f,
                0f, 0.015f, 1.07f, 0f, 8f,
                0f, 0f, 0f, 1f, 0f
            )
            else -> floatArrayOf(
                1f, 0f, 0f, 0f, 0f,
                0f, 1f, 0f, 0f, 0f,
                0f, 0f, 1f, 0f, 0f,
                0f, 0f, 0f, 1f, 0f
            )
        }

        val result = ColorMatrix()
        result.setSaturation(saturation)
        result.postConcat(ColorMatrix(tone))
        return result
    }
}
