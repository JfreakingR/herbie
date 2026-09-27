package com.prismml.herbiebrain

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Settings
import android.util.Log
import androidx.core.content.ContextCompat

class HerbieBootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED) return
        val token = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
            .getString(TOKEN_KEY, null)
            ?.trim()
        if (token.isNullOrEmpty()) return
        // A service started from here never gets the microphone, so Herbie
        // would wake unable to hear. With "Appear on top" granted, Android lets
        // the app open its own screen at boot; the service then starts from the
        // foreground with the microphone and the screen steps back.
        if (Settings.canDrawOverlays(context)) {
            try {
                context.startActivity(
                    Intent(context, MainActivity::class.java)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        .putExtra(MainActivity.EXTRA_FROM_BOOT, true),
                )
                return
            } catch (refused: Exception) {
                Log.w(TAG, "Could not open at boot; starting without ears", refused)
            }
        }
        ContextCompat.startForegroundService(
            context,
            Intent(context, HerbieModelService::class.java),
        )
    }

    companion object {
        private const val PREFERENCES = "herbie_private_bridge"
        private const val TOKEN_KEY = "bridge_token"
        private const val TAG = "HerbieBootReceiver"
    }
}
