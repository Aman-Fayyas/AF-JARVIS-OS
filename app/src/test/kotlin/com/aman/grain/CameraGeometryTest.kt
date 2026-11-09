package com.aman.grain

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class CameraGeometryTest {
    @Test
    fun portraitFourByThreeCropKeepsCenterAndFullHeight() {
        assertArrayEquals(intArrayOf(875, 0, 2250, 3000),
            CameraGeometry.centerCropRect(4000, 3000, 0.75f))
    }

    @Test
    fun portraitNineBySixteenCropKeepsCenterAndFullHeight() {
        assertArrayEquals(intArrayOf(1156, 0, 1688, 3000),
            CameraGeometry.centerCropRect(4000, 3000, 9f / 16f))
    }

    @Test
    fun landscapeSixteenByNineCropKeepsCenterAndFullWidth() {
        assertArrayEquals(intArrayOf(0, 1156, 3000, 1688),
            CameraGeometry.centerCropRect(3000, 4000, 16f / 9f))
    }

    @Test
    fun jpegOrientationUsesCamera2ConventionForFrontAndBack() {
        assertEquals(90, CameraGeometry.jpegOrientation(90, 0, false))
        assertEquals(0, CameraGeometry.jpegOrientation(90, 90, false))
        assertEquals(180, CameraGeometry.jpegOrientation(90, 90, true))
        assertEquals(0, CameraGeometry.jpegOrientation(270, 90, true))
        assertEquals(180, CameraGeometry.jpegOrientation(270, 270, true))
    }

    @Test
    fun fullFrameDoesNotCrop() {
        assertNull(CameraGeometry.centerCropRect(4000, 3000, 0f))
        assertNull(CameraGeometry.centerCropRect(4000, 3000, 4f / 3f))
    }
}
