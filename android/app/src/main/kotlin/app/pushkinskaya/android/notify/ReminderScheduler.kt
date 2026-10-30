package app.pushkinskaya.android.notify

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import app.pushkinskaya.android.R

/**
 * Route reminders must fire at the chosen time even if the phone is idle, so
 * they go through AlarmManager rather than WorkManager: WorkManager work is
 * batched and Doze can defer it for hours, which is useless for "remind me in
 * 15 minutes". WorkManager is still the right tool for the periodic status
 * check, where a late run is harmless.
 */
class ReminderReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val firstStop = intent.getStringExtra(EXTRA_FIRST_STOP) ?: return
        Notifications.show(
            context = context,
            id = REMINDER_ID,
            channel = Notifications.CHANNEL_REMINDERS,
            title = context.getString(R.string.reminder_title),
            text = context.getString(R.string.reminder_text, firstStop),
            deepLink = "pushkinskaya://routes",
        )
    }

    companion object {
        const val EXTRA_FIRST_STOP = "first_stop"
        const val REMINDER_ID = 1001
    }
}

object ReminderScheduler {
    private const val REQUEST_CODE = ReminderReceiver.REMINDER_ID

    fun schedule(context: Context, delayMinutes: Long, firstStopName: String) {
        val alarmManager = context.getSystemService(AlarmManager::class.java)
        val triggerAt = System.currentTimeMillis() + delayMinutes * 60_000L
        val pending = pendingIntent(context, firstStopName)

        // Exact alarms need a user-granted special permission on Android 12+.
        // When it is not granted, setAndAllowWhileIdle still fires while idle,
        // just not to the exact minute — better than silently not reminding.
        val canBeExact = Build.VERSION.SDK_INT < Build.VERSION_CODES.S ||
            alarmManager.canScheduleExactAlarms()
        if (canBeExact) {
            alarmManager.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pending)
        } else {
            alarmManager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pending)
        }
    }

    fun cancel(context: Context) {
        val alarmManager = context.getSystemService(AlarmManager::class.java)
        alarmManager.cancel(pendingIntent(context, null))
    }

    private fun pendingIntent(context: Context, firstStopName: String?): PendingIntent {
        val intent = Intent(context, ReminderReceiver::class.java).apply {
            putExtra(ReminderReceiver.EXTRA_FIRST_STOP, firstStopName)
        }
        return PendingIntent.getBroadcast(
            context,
            REQUEST_CODE,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }
}
