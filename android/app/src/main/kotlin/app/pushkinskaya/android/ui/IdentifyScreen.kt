package app.pushkinskaya.android.ui

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import app.pushkinskaya.android.AppContainer
import app.pushkinskaya.android.R
import app.pushkinskaya.android.data.IdentifyRepository
import app.pushkinskaya.android.data.LandmarkRepository
import app.pushkinskaya.android.data.PredictResponse
import app.pushkinskaya.android.data.userMessage
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.io.File
import kotlin.math.roundToInt

sealed interface IdentifyState {
    data object Idle : IdentifyState
    data object Loading : IdentifyState
    data class Done(val result: PredictResponse) : IdentifyState
    data class Failed(val message: String) : IdentifyState
}

class IdentifyViewModel(
    private val identify: IdentifyRepository,
    landmarks: LandmarkRepository,
) : ViewModel() {
    private val _state = MutableStateFlow<IdentifyState>(IdentifyState.Idle)
    val state: StateFlow<IdentifyState> = _state

    /** id to English name, used to label the candidate list. */
    val names: StateFlow<Map<String, String>> =
        landmarks.landmarks.map { list -> list.associate { it.id to it.name } }
            .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyMap())

    fun identify(photo: Uri) {
        viewModelScope.launch {
            _state.value = IdentifyState.Loading
            identify.identify(photo)
                .onSuccess { _state.value = IdentifyState.Done(it) }
                .onFailure { _state.value = IdentifyState.Failed(it.userMessage()) }
        }
    }
}

@Composable
fun IdentifyScreen(container: AppContainer, onOpen: (String) -> Unit) {
    val vm: IdentifyViewModel = viewModel(
        factory = simpleFactory { IdentifyViewModel(container.identify, container.landmarks) },
    )
    val state by vm.state.collectAsStateWithLifecycle()
    val names by vm.names.collectAsStateWithLifecycle()
    val context = LocalContext.current

    val gallery = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
        if (uri != null) vm.identify(uri)
    }
    var cameraUri by remember { mutableStateOf<Uri?>(null) }
    val camera = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { saved ->
        val uri = cameraUri
        if (saved && uri != null) vm.identify(uri)
    }

    Column(
        Modifier.fillMaxSize().statusBarsPadding().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Button(
            onClick = {
                val dir = File(context.cacheDir, "images").apply { mkdirs() }
                val uri = FileProvider.getUriForFile(context, "${context.packageName}.files", File(dir, "capture.jpg"))
                cameraUri = uri
                camera.launch(uri)
            },
            modifier = Modifier.fillMaxWidth(),
        ) { Text(stringResource(R.string.take_photo)) }

        OutlinedButton(
            onClick = { gallery.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) },
            modifier = Modifier.fillMaxWidth(),
        ) { Text(stringResource(R.string.choose_photo)) }

        when (val s = state) {
            IdentifyState.Idle -> Unit
            IdentifyState.Loading -> {
                CircularProgressIndicator()
                Text(stringResource(R.string.identifying))
            }
            is IdentifyState.Failed -> Text(s.message, color = MaterialTheme.colorScheme.error)
            is IdentifyState.Done -> {
                val result = s.result
                val id = result.landmarkId
                if (result.identified && id != null) {
                    Text(
                        stringResource(
                            R.string.identified_as,
                            result.name ?: names[id] ?: id,
                            (result.confidence * 100).roundToInt(),
                        ),
                        style = MaterialTheme.typography.titleLarge,
                    )
                    Button(onClick = { onOpen(id) }) { Text(stringResource(R.string.open_details)) }
                } else {
                    Text(stringResource(R.string.not_sure), style = MaterialTheme.typography.titleMedium)
                    if (result.top5.isNotEmpty()) {
                        Text(stringResource(R.string.possible_matches), style = MaterialTheme.typography.labelLarge)
                        result.top5.take(3).forEach { candidate ->
                            Text(
                                text = "${names[candidate.landmarkId] ?: candidate.landmarkId} (${(candidate.confidence * 100).roundToInt()}%)",
                                modifier = Modifier.clickable { onOpen(candidate.landmarkId) }.padding(vertical = 6.dp),
                            )
                        }
                    }
                }
            }
        }
    }
}
