package app.pushkinskaya.android.ui

import android.Manifest
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
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
import app.pushkinskaya.android.data.PlanResponse
import app.pushkinskaya.android.data.RouteRepository
import app.pushkinskaya.android.data.Settings
import app.pushkinskaya.android.data.userMessage
import app.pushkinskaya.android.notify.Notifications
import app.pushkinskaya.android.notify.ReminderScheduler
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.util.Locale

data class RoutesUi(
    val items: List<LandmarkEntity> = emptyList(),
    val language: String = "en",
    val plan: PlanResponse? = null,
    val planning: Boolean = false,
    val error: String? = null,
    val optimize: Boolean = true,
)

private data class PlanState(
    val plan: PlanResponse? = null,
    val planning: Boolean = false,
    val error: String? = null,
    val optimize: Boolean = true,
)

class RoutesViewModel(
    private val routes: RouteRepository,
    landmarks: LandmarkRepository,
    settings: Settings,
) : ViewModel() {
    private val planState = MutableStateFlow(PlanState())

    val ui: StateFlow<RoutesUi> = combine(
        routes.items, landmarks.landmarks, settings.language, planState,
    ) { items, all, language, plan ->
        val byId = all.associateBy { it.id }
        RoutesUi(
            items = items.mapNotNull { byId[it.landmarkId] },
            language = language,
            plan = plan.plan,
            planning = plan.planning,
            error = plan.error,
            optimize = plan.optimize,
        )
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), RoutesUi())

    fun setOptimize(value: Boolean) = planState.update { it.copy(optimize = value) }

    fun remove(id: String) {
        viewModelScope.launch {
            routes.remove(id)
            planState.update { it.copy(plan = null) }
        }
    }

    fun clear() {
        viewModelScope.launch {
            routes.clear()
            planState.update { it.copy(plan = null, error = null) }
        }
    }

    fun plan() {
        val ids = ui.value.items.map { it.id }
        if (ids.isEmpty()) return
        viewModelScope.launch {
            planState.update { it.copy(planning = true, error = null) }
            routes.plan(ids, planState.value.optimize)
                .onSuccess { result -> planState.update { it.copy(plan = result, planning = false) } }
                .onFailure { e -> planState.update { it.copy(error = e.userMessage(), planning = false) } }
        }
    }
}

@Composable
fun RoutesScreen(container: AppContainer) {
    val vm: RoutesViewModel = viewModel(
        factory = simpleFactory { RoutesViewModel(container.routes, container.landmarks, container.settings) },
    )
    val ui by vm.ui.collectAsStateWithLifecycle()
    val context = LocalContext.current

    var message by remember { mutableStateOf<String?>(null) }
    var pendingMinutes by remember { mutableStateOf<Long?>(null) }

    fun scheduleReminder(minutes: Long) {
        val first = ui.items.firstOrNull() ?: return
        ReminderScheduler.schedule(context, minutes, displayName(first, ui.language))
        message = context.getString(R.string.reminder_set)
    }

    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        val minutes = pendingMinutes
        pendingMinutes = null
        if (granted && minutes != null) {
            scheduleReminder(minutes)
        } else {
            message = context.getString(R.string.reminder_needs_permission)
        }
    }

    fun remind(minutes: Long) {
        if (ui.items.isEmpty()) return
        if (Notifications.canPost(context)) {
            scheduleReminder(minutes)
        } else if (Build.VERSION.SDK_INT >= 33) {
            // Ask at the moment the user actually wants a reminder, not at launch.
            pendingMinutes = minutes
            permission.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    Column(Modifier.fillMaxSize().statusBarsPadding().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        if (ui.items.isEmpty()) {
            Text(stringResource(R.string.routes_empty), style = MaterialTheme.typography.bodyLarge)
            return@Column
        }

        LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            items(ui.items, key = { it.id }) { landmark ->
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(displayName(landmark, ui.language), style = MaterialTheme.typography.titleSmall)
                        StatusBadge(landmark.status)
                    }
                    IconButton(onClick = { vm.remove(landmark.id) }) {
                        Icon(Icons.Default.Delete, contentDescription = stringResource(R.string.remove_from_route))
                    }
                }
            }
            val plan = ui.plan
            if (plan != null) {
                item {
                    Column(Modifier.padding(top = 12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        plan.stops.forEachIndexed { index, stop ->
                            Text(stringResource(R.string.stop_line, index + 1, stop.name, stop.visitMinutes))
                        }
                        Text(
                            stringResource(
                                R.string.plan_total,
                                format(plan.totalMinutes), format(plan.walkingMinutes), format(plan.visitingMinutes),
                            ),
                            style = MaterialTheme.typography.titleSmall,
                        )
                    }
                }
            }
        }

        ui.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        message?.let { Text(it, style = MaterialTheme.typography.bodySmall) }

        Row(verticalAlignment = Alignment.CenterVertically) {
            Switch(checked = ui.optimize, onCheckedChange = vm::setOptimize)
            Text(stringResource(R.string.optimize_order), Modifier.padding(start = 8.dp))
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            Button(onClick = vm::plan, enabled = !ui.planning) { Text(stringResource(R.string.plan_route)) }
            OutlinedButton(onClick = vm::clear) { Text(stringResource(R.string.clear_route)) }
            if (ui.planning) CircularProgressIndicator(Modifier.padding(start = 4.dp))
        }

        Text(stringResource(R.string.remind_me), style = MaterialTheme.typography.labelLarge)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = { remind(15) }) { Text(stringResource(R.string.remind_15)) }
            OutlinedButton(onClick = { remind(60) }) { Text(stringResource(R.string.remind_60)) }
            OutlinedButton(onClick = { remind(180) }) { Text(stringResource(R.string.remind_180)) }
        }
    }
}

private fun format(value: Double): String = String.format(Locale.getDefault(), "%.0f", value)
