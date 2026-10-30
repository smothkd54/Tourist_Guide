package app.pushkinskaya.android.util

import android.content.Context
import android.speech.tts.TextToSpeech
import java.util.Locale

/** Reads a description aloud with Android's built-in text-to-speech. Descriptions are English. */
class Speaker(context: Context) : TextToSpeech.OnInitListener {
    private val tts = TextToSpeech(context.applicationContext, this)
    private var ready = false

    override fun onInit(status: Int) {
        ready = status == TextToSpeech.SUCCESS
        if (ready) tts.language = Locale.ENGLISH
    }

    fun speak(text: String) {
        if (ready) tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "landmark")
    }

    fun stop() {
        tts.stop()
    }

    fun release() {
        tts.stop()
        tts.shutdown()
    }
}
