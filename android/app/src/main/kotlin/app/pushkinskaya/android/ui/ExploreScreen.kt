package app.pushkinskaya.android.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Check
import androidx.compose.material3.Card
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import app.pushkinskaya.android.AppContainer
import app.pushkinskaya.android.R
import app.pushkinskaya.android.data.LandmarkEntity
import app.pushkinskaya.android.data.LandmarkRepository
import app.pushkinskaya.android.data.RouteRepository
import app.pushkinskaya.android.data.Settings
import app.pushkinskaya.android.data.userMessage
import coil.compose.AsyncImage
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

data class LandmarkRow(val landmark: LandmarkEntity, val onRoute: Boolean)

data class ExploreUi(
    val rows: List<LandmarkRow> = emptyList(),
    val query: String = "",
    val loading: Boolean = false,
    val error: String? = null,
    val language: String = "en",
)

class ExploreViewModel(
    private val landmarks: LandmarkRepository,
    private val routes: RouteRepository,
    settings: Settings,
) : ViewModel() {
    private val query = MutableStateFlow("")
    private val loading = MutableStateFlow(false)
    private val error = MutableStateFlow<String?>(null)

    val ui: StateFlow<ExploreUi> = combine(
        combine(landmarks.landmarks, routes.items, settings.language, query) { all, route, lang, q ->
            val onRoute = route.map { it.landmarkId }.toSet()
            val shown = all.filter {
                q.isBlank() || it.name.contains(q, ignoreCase = true) || it.nameRu.contains(q, ignoreCase = true)
            }
            Triple(shown.map { LandmarkRow(it, it.id in onRoute) }, lang, q)
        },
        loading,
        error,
    ) { (rows, lang, q), isLoading, err ->
        ExploreUi(rows, q, isLoading, err, lang)
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), ExploreUi())

    init {
        refresh()
    }

    fun setQuery(value: String) {
        query.value = value
    }

    fun refresh() {
        viewModelScope.launch {
            loading.value = true
            landmarks.refresh()
                .onSuccess { error.value = null }
                .onFailure { error.value = it.userMessage() }
            loading.value = false
        }
    }

    fun toggle(row: LandmarkRow) {
        viewModelScope.launch {
            if (row.onRoute) routes.remove(row.landmark.id) else routes.add(row.landmark.id)
        }
    }
}

@Composable
fun ExploreScreen(container: AppContainer, onOpen: (String) -> Unit) {
    val vm: ExploreViewModel = viewModel(
        factory = simpleFactory { ExploreViewModel(container.landmarks, container.routes, container.settings) },
    )
    val ui by vm.ui.collectAsStateWithLifecycle()
    val error = ui.error

    Column(Modifier.fillMaxSize().statusBarsPadding()) {
        OutlinedTextField(
            value = ui.query,
            onValueChange = vm::setQuery,
            singleLine = true,
            label = { Text(stringResource(R.string.search_hint)) },
            modifier = Modifier.fillMaxWidth().padding(12.dp),
        )
        if (ui.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
        if (error != null) {
            val text = if (ui.rows.isNotEmpty()) stringResource(R.string.offline_banner, error) else error
            Text(
                text = text,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp).clickable { vm.refresh() },
            )
        }
        LazyColumn(Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            items(ui.rows, key = { it.landmark.id }) { row ->
                LandmarkCard(
                    row = row,
                    language = ui.language,
                    photoUrl = container.photoUrl(row.landmark.id),
                    onOpen = { onOpen(row.landmark.id) },
                    onToggle = { vm.toggle(row) },
                )
            }
        }
    }
}

@Composable
private fun LandmarkCard(
    row: LandmarkRow,
    language: String,
    photoUrl: String,
    onOpen: () -> Unit,
    onToggle: () -> Unit,
) {
    Card(Modifier.fillMaxWidth().padding(horizontal = 12.dp).clickable(onClick = onOpen)) {
        Row(Modifier.padding(10.dp), verticalAlignment = Alignment.CenterVertically) {
            AsyncImage(
                model = photoUrl,
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.size(72.dp).clip(RoundedCornerShape(8.dp)),
            )
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    text = displayName(row.landmark, language),
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = row.landmark.type,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                StatusBadge(row.landmark.status)
            }
            IconButton(onClick = onToggle) {
                Icon(
                    imageVector = if (row.onRoute) Icons.Default.Check else Icons.Default.Add,
                    contentDescription = stringResource(
                        if (row.onRoute) R.string.remove_from_route else R.string.add_to_route,
                    ),
                )
            }
        }
    }
}
