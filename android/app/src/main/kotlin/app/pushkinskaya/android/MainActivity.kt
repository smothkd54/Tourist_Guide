package app.pushkinskaya.android

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import app.pushkinskaya.android.ui.AppRoot
import app.pushkinskaya.android.ui.AppTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val container = (application as PushkinskayaApp).container
        setContent {
            AppTheme { AppRoot(container) }
        }
    }
}
