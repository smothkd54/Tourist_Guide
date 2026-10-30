package app.pushkinskaya.android.notify

import android.content.Context
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import app.pushkinskaya.android.PushkinskayaApp
import app.pushkinskaya.android.R
import app.pushkinskaya.android.ui.statusLabel
import java.util.concurrent.TimeUnit

/**
 * Polls the server every 6 hours and notifies when a landmark on the visit list changes status.
 * This is the free alternative to remote push: no provider, but alerts arrive hours late, not instantly.
 */
class StatusCheckWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        val container = (applicationContext as PushkinskayaApp).container
        val outcome = container.landmarks.refresh()
        outcome.getOrNull()?.forEach { change ->
            Notifications.show(
                context = applicationContext,
                id = change.id.hashCode(),
                channel = Notifications.CHANNEL_STATUS,
                title = applicationContext.getString(R.string.status_title),
                text = applicationContext.getString(
                    R.string.status_text, change.name, statusLabel(applicationContext, change.status),
                ),
                deepLink = "pushkinskaya://landmark/${change.id}",
            )
        }
        return if (outcome.isSuccess) Result.success() else Result.retry()
    }
}

object StatusCheckScheduler {
    fun schedule(context: Context) {
        val request = PeriodicWorkRequestBuilder<StatusCheckWorker>(6, TimeUnit.HOURS)
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .build()
        WorkManager.getInstance(context)
            .enqueueUniquePeriodicWork("status-check", ExistingPeriodicWorkPolicy.KEEP, request)
    }
}
