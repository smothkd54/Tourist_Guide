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
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
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
import app.pushkinskaya.android.data.RouteRepository
import app.pushkinskaya.android.data.Settings
import app.pushkinskaya.android.util.Speaker
import coil.compose.AsyncImage
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class DetailViewModel(
    private val landmarkId: String,
    landmarks: LandmarkRepository,
    private val routes: RouteRepository,
    settings: Settings,
) : ViewModel() {
    val landmark: StateFlow<LandmarkEntity?> =
        landmarks.landmark(landmarkId).stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    val onRoute: StateFlow<Boolean> =
        routes.items.map { items -> items.any { it.landmarkId == landmarkId } }
            .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), false)

    val language: StateFlow<String> =
        settings.language.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), "en")

    fun toggleRoute() {
        viewModelScope.launch {
            if (onRoute.value) routes.remove(landmarkId) else routes.add(landmarkId)
        }
    }
}

@Composable
fun DetailScreen(container: AppContainer, id: String, onBack: () -> Unit) {
    val vm: DetailViewModel = viewModel(
        key = "detail-$id",
        factory = simpleFactory { DetailViewModel(id, container.landmarks, container.routes, container.settings) },
    )
    val landmark by vm.landmark.collectAsStateWithLifecycle()
    val onRoute by vm.onRoute.collectAsStateWithLifecycle()
    val language by vm.language.collectAsStateWithLifecycle()

    val context = LocalContext.current
    val speaker = remember { Speaker(context) }
    var speaking by remember { mutableStateOf(false) }
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
        }
    }
}
