package app.pushkinskaya.android.ui

import android.content.Intent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import app.pushkinskaya.android.AppContainer
import app.pushkinskaya.android.R
import app.pushkinskaya.android.data.userMessage
import kotlinx.coroutines.launch

@Composable
fun MoreScreen(container: AppContainer) {
    val language by container.settings.language.collectAsStateWithLifecycle(initialValue = "en")
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var refreshMessage by remember { mutableStateOf<String?>(null) }

    Column(
        Modifier.fillMaxSize().statusBarsPadding().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(stringResource(R.string.language), style = MaterialTheme.typography.titleSmall)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            LanguageButton("EN", selected = language == "en") { scope.launch { container.settings.setLanguage("en") } }
            LanguageButton("RU", selected = language == "ru") { scope.launch { container.settings.setLanguage("ru") } }
        }

        OutlinedButton(onClick = {
            scope.launch {
                refreshMessage = container.landmarks.refresh().fold(
                    onSuccess = { null },
                    onFailure = { it.userMessage() },
                )
            }
        }) { Text(stringResource(R.string.refresh_now)) }
        refreshMessage?.let { Text(it, color = MaterialTheme.colorScheme.error) }

        OutlinedButton(onClick = {
            val intent = Intent(android.provider.Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                .putExtra(android.provider.Settings.EXTRA_APP_PACKAGE, context.packageName)
            context.startActivity(intent)
        }) { Text(stringResource(R.string.notification_settings)) }

        Text(
            stringResource(R.string.photo_credits_note),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun LanguageButton(label: String, selected: Boolean, onClick: () -> Unit) {
    if (selected) Button(onClick = onClick) { Text(label) } else OutlinedButton(onClick = onClick) { Text(label) }
}
