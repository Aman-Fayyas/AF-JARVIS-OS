# Grain Camera

A lightweight, native Android camera app focused on the Samsung Galaxy S9+ first, with Android 10 / API 29 as its minimum version. It is also designed to run on newer Galaxy phones such as the S23 Ultra.

## Design goals

- Native Kotlin and Android framework APIs; no Jetpack Compose, web runtime, account, cloud AI, or analytics SDK.
- Direct Camera2 capture path with runtime capability checks.
- Still capture saves a sensor DNG when the active camera and stream combination support RAW, plus an original JPEG.
- When a look is selected, a separately processed JPEG is saved beside the original JPEG and DNG. The DNG is never modified by the filter engine.
- Looks included: Golden Hour, Soft Film, Cinematic, Cool Fade, and Mono.
- Manual ISO, shutter, white balance presets, and manual focus are exposed only when the active camera reports the relevant capability.
- Standard H.264 MP4 video capture. Video is not sensor-RAW and can still include normal camera ISP processing.
- Media is saved to DCIM/Grain Camera.

## Compatibility notes

Android Camera2 capabilities vary by camera ID, lens, firmware, and supported output-stream combinations. Grain checks the active rear/front camera at runtime. If a camera advertises RAW but cannot configure a simultaneous preview + JPEG + RAW session, the app falls back to JPEG capture and reports that RAW is unavailable for that session.

On a Galaxy S9+, choose the rear camera for the primary RAW workflow. On a Galaxy S23 Ultra, this first version intentionally uses a still-image stream close to 12 MP to avoid creating very large RAW buffers on a memory-constrained session. Future versions can add a selectable high-resolution RAW mode after on-device validation.

Filters are a JPEG rendering step, not a live optical preview effect. Each processed JPEG has its own file. The corresponding DNG remains sensor data for later editing.

## Build

Requires JDK 17, Gradle 8.9, Android SDK platform 35, and build tools 35.0.0.

    gradle testDebugUnitTest assembleDebug lint

The GitHub Actions workflow builds and uploads app-debug.apk as the grain-camera-debug artifact.
