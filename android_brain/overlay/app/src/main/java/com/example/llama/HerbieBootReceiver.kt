package com.prismml.herbiebrain

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat

class HerbieBootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED) return
        val token = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
            .getString(TOKEN_KEY, null)
            ?.trim()
        if (!token.isNullOrEmpty()) {
            ContextCompat.startForegroundService(
                context,
                Intent(context, HerbieModelService::class.java),
            )
        }
    }

    companion object {
        private const val PREFERENCES = "herbie_private_bridge"
        private const val TOKEN_KEY = "bridge_token"
    }
}
