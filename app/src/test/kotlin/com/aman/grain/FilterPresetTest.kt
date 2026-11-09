package com.aman.grain

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class FilterPresetTest {
    @Test
    fun presetsHaveUniqueExportTags() {
        val tags = FilterPreset.values().map { it.fileTag }
        assertEquals(tags.size, tags.toSet().size)
    }

    @Test
    fun originalIsTheDefaultUnfilteredPreset() {
        assertEquals(FilterPreset.ORIGINAL, FilterPreset.values().first())
        assertTrue(FilterPreset.values().size >= 14)
    }

    @Test
    fun everyNonOriginalPresetHasAUniqueDisplayName() {
        val names = FilterPreset.values().map { it.title.lowercase() }
        assertEquals(names.size, names.toSet().size)
    }
}
