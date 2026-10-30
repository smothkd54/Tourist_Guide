package app.pushkinskaya.android.ui

import android.content.Context
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import app.pushkinskaya.android.R
import app.pushkinskaya.android.data.LandmarkEntity
import app.pushkinskaya.android.data.isNotOpen

@Composable
fun AppTheme(content: @Composable () -> Unit) {
    val colors = if (isSystemInDarkTheme()) {
        darkColorScheme(primary = Color(0xFFC8A96E))
    } else {
        lightColorScheme(primary = Color(0xFF8A6A1F))
    }
    MaterialTheme(colorScheme = colors, content = content)
}

fun displayName(landmark: LandmarkEntity, language: String): String =
    if (language == "ru" && landmark.nameRu.isNotBlank()) landmark.nameRu else landmark.name

fun statusLabel(context: Context, status: String?): String =
    context.getString(
        when (status) {
            "closed" -> R.string.status_closed
            "temporarily_closed" -> R.string.status_temporarily_closed
            else -> R.string.status_open
        },
    )

@Composable
fun StatusBadge(status: String?) {
    if (!isNotOpen(status)) return
    Surface(
        color = MaterialTheme.colorScheme.errorContainer,
        shape = RoundedCornerShape(6.dp),
    ) {
        Text(
            text = statusLabel(LocalContext.current, status),
            color = MaterialTheme.colorScheme.onErrorContainer,
            style = MaterialTheme.typography.labelSmall,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
        )
    }
}

/** Small factory so ViewModels can take repositories without a DI framework. */
inline fun <VM : ViewModel> simpleFactory(crossinline build: () -> VM): ViewModelProvider.Factory =
    object : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T = build() as T
    }
