package app.pushkinskaya.android.data

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import retrofit2.HttpException
import java.io.IOException

@Serializable
private data class ErrorBody(val error: String? = null)

private val errorJson = Json { ignoreUnknownKeys = true }

/** The Flask API returns {"error": "..."}; show that text, or a plain fallback. */
fun Throwable.userMessage(): String = when (this) {
    is HttpException -> {
        val body = response()?.errorBody()?.string()
        val text = body?.let { runCatching { errorJson.decodeFromString<ErrorBody>(it).error }.getOrNull() }
        text ?: "Server error (HTTP ${code()})"
    }
    is IOException -> "No connection. Check your internet and try again."
    else -> message ?: "Something went wrong."
}

