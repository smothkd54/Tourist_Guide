package app.pushkinskaya.android.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "settings")

class Settings(private val context: Context) {
    private val languageKey = stringPreferencesKey("language")

    /** "en" or "ru". Only landmark names switch, like the web app. */
    val language: Flow<String> = context.dataStore.data.map { it[languageKey] ?: "en" }

    suspend fun setLanguage(language: String) {
        context.dataStore.edit { it[languageKey] = language }
    }
}
