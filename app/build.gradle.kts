plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.aman.grain"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.aman.grain"
        minSdk = 29
        targetSdk = 35
        versionCode = 3
        versionName = "0.2.0"
        testInstrumentationRunner = "android.test.runner.AndroidJUnitRunner"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
        debug {
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
        }
    }

    testOptions {
        unitTests.isReturnDefaultValues = true
    }
}

dependencies {
    implementation("androidx.camera.viewfinder:viewfinder-view:1.6.2")
    implementation("androidx.camera.viewfinder:viewfinder-core:1.6.2")
    testImplementation("junit:junit:4.13.2")
}
