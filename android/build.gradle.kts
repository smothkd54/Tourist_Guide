// Versions are my best guess and were NOT checked against Google or Maven repositories.
// Safest path: create a new "Empty Activity (Compose)" project in Android Studio, keep its
// plugin versions, then copy the app/src folder and the dependencies block from here.
plugins {
    id("com.android.application") version "8.7.3" apply false
    id("org.jetbrains.kotlin.android") version "2.0.21" apply false
    id("org.jetbrains.kotlin.plugin.compose") version "2.0.21" apply false
    id("org.jetbrains.kotlin.plugin.serialization") version "2.0.21" apply false
    id("com.google.devtools.ksp") version "2.0.21-1.0.28" apply false
}
