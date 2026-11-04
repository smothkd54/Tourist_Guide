package app.pushkinskaya.android.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import app.pushkinskaya.android.AppContainer
import app.pushkinskaya.android.R
import app.pushkinskaya.android.data.LandmarkEntity
import app.pushkinskaya.android.data.LandmarkRepository
import app.pushkinskaya.android.data.ReportRepository
import app.pushkinskaya.android.data.RouteRepository
import app.pushkinskaya.android.data.Settings
import app.pushkinskaya.android.util.Speaker
import coil.compose.AsyncImage
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/** API value paired with the string resource shown in the dialog. */
private val REPORT_CATEGORIES = listOf(
    "wrong_photo" to R.string.report_wrong_photo,
    "wrong_info" to R.string.report_wrong_info,
    "closed" to R.string.report_closed,
    "other" to R.string.report_other,
)

sealed class ReportState {
    object Idle : ReportState()
    object Sending : ReportState()
    object Sent : ReportState()
    object Failed : ReportState()
}

class DetailViewModel(
    private val landmarkId: String,
    landmarks: LandmarkRepository,
    private val routes: RouteRepository,
    private val reports: ReportRepository,
    settings: Settings,
) : ViewModel() {
    val landmark: StateFlow<LandmarkEntity?> =
        landmarks.landmark(landmarkId).stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    val onRoute: StateFlow<Boolean> =
        routes.items.map { items -> items.any { it.landmarkId == landmarkId } }
            .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), false)

    val language: StateFlow<String> =
        settings.language.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), "en")

    var reportState by mutableStateOf<ReportState>(ReportState.Idle)
        private set

    fun toggleRoute() {
        viewModelScope.launch {
            if (onRoute.value) routes.remove(landmarkId) else routes.add(landmarkId)
        }
    }

    fun submitReport(category: String, message: String) {
        if (reportState is ReportState.Sending) return
        reportState = ReportState.Sending
        viewModelScope.launch {
            reportState = reports.submit(landmarkId, category, message).fold(
                onSuccess = { ReportState.Sent },
                onFailure = { ReportState.Failed },
            )
        }
    }

    fun resetReport() {
        reportState = ReportState.Idle
    }
}

@Composable
fun DetailScreen(container: AppContainer, id: String, onBack: () -> Unit) {
    val vm: DetailViewModel = viewModel(
        key = "detail-$id",
        factory = simpleFactory {
            DetailViewModel(id, container.landmarks, container.routes, container.reports, container.settings)
        },
    )
    val landmark by vm.landmark.collectAsStateWithLifecycle()
    val onRoute by vm.onRoute.collectAsStateWithLifecycle()
    val language by vm.language.collectAsStateWithLifecycle()

    val context = LocalContext.current
    val speaker = remember { Speaker(context) }
    var speaking by remember { mutableStateOf(false) }
    var showReport by remember { mutableStateOf(false) }
    DisposableEffect(Unit) { onDispose { speaker.release() } }

    Column(Modifier.fillMaxSize().statusBarsPadding()) {
        IconButton(onClick = onBack) {
            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = stringResource(R.string.back))
        }
        val lm = landmark
        if (lm == null) {
            CircularProgressIndicator(Modifier.padding(24.dp))
            return@Column
        }
        Column(
            Modifier.verticalScroll(rememberScrollState()).padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            AsyncImage(
                model = container.photoUrl(lm.id),
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxWidth().height(220.dp),
            )
            // Credit is part of the publishing rule, not decoration.
            lm.photoCredit?.let { credit ->
                Text(
                    text = stringResource(R.string.photo_credit, credit),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Text(displayName(lm, language), style = MaterialTheme.typography.headlineSmall)
            StatusBadge(lm.status)
            Text(lm.address, color = MaterialTheme.colorScheme.onSurfaceVariant)
            lm.yearBuilt?.let { Text(stringResource(R.string.year_built, it)) }
            if (lm.style.isNotBlank()) Text(lm.style)
            if (lm.architect.isNotBlank()) Text(lm.architect)
            Text(lm.description, style = MaterialTheme.typography.bodyLarge)
            if (lm.funFact.isNotBlank()) Text(lm.funFact, style = MaterialTheme.typography.bodyMedium)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                OutlinedButton(onClick = {
                    if (speaking) speaker.stop() else speaker.speak("${lm.name}. ${lm.description}")
                    speaking = !speaking
                }) {
                    Text(stringResource(if (speaking) R.string.stop else R.string.listen))
                }
                Button(onClick = vm::toggleRoute) {
                    Text(stringResource(if (onRoute) R.string.remove_from_route else R.string.add_to_route))
                }
            }
            OutlinedButton(
                onClick = {
                    vm.resetReport()
                    showReport = true
                },
                modifier = Modifier.padding(bottom = 24.dp),
            ) {
                Text(stringResource(R.string.report_problem))
            }
        }

        if (showReport) {
            ReportDialog(
                state = vm.reportState,
                onDismiss = {
                    showReport = false
                    vm.resetReport()
                },
                onSubmit = vm::submitReport,
            )
        }
    }
}

@Composable
private fun ReportDialog(
    state: ReportState,
    onDismiss: () -> Unit,
    onSubmit: (category: String, message: String) -> Unit,
) {
    var category by remember { mutableStateOf(REPORT_CATEGORIES.first().first) }
    var message by remember { mutableStateOf("") }

    val sending = state is ReportState.Sending
    val sent = state is ReportState.Sent
    val failed = state is ReportState.Failed
    val longEnough = message.trim().length >= 10

    AlertDialog(
        onDismissRequest = { if (!sending) onDismiss() },
        title = { Text(stringResource(if (sent) R.string.report_sent_title else R.string.report_title)) },
        text = {
            if (sent) {
                Text(stringResource(R.string.report_thanks))
            } else {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(
                        stringResource(R.string.report_category),
                        style = MaterialTheme.typography.labelLarge,
                    )
                    REPORT_CATEGORIES.forEach { (value, labelRes) ->
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            RadioButton(
                                selected = category == value,
                                onClick = { category = value },
                                enabled = !sending,
                            )
                            Text(stringResource(labelRes))
                        }
                    }
                    OutlinedTextField(
                        value = message,
                        onValueChange = { if (it.length <= 2000) message = it },
                        label = { Text(stringResource(R.string.report_message_hint)) },
                        minLines = 3,
                        enabled = !sending,
                        isError = failed,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    if (failed) {
                        Text(
                            stringResource(R.string.report_failed),
                            color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.bodySmall,
                        )
                    } else if (message.isNotEmpty() && !longEnough) {
                        Text(
                            stringResource(R.string.report_min_length),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Text(
                        stringResource(R.string.report_anonymous_note),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        },
        confirmButton = {
            if (sent) {
                TextButton(onClick = onDismiss) {
                    Text(stringResource(R.string.report_close))
                }
            } else {
                Button(
                    onClick = { onSubmit(category, message.trim()) },
                    enabled = !sending && longEnough,
                ) {
                    Text(stringResource(if (sending) R.string.report_sending else R.string.report_send))
                }
            }
        },
        dismissButton = {
            if (!sent) {
                TextButton(onClick = onDismiss, enabled = !sending) {
                    Text(stringResource(R.string.report_cancel))
                }
            }
        },
    )
}
