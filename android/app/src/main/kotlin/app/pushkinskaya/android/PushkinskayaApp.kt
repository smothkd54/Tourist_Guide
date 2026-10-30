package app.pushkinskaya.android

import android.app.Application
import android.content.Context
import androidx.room.Room
import app.pushkinskaya.android.data.Api
import app.pushkinskaya.android.data.AppDatabase
import app.pushkinskaya.android.data.IdentifyRepository
import app.pushkinskaya.android.data.LandmarkRepository
import app.pushkinskaya.android.data.RouteRepository
import app.pushkinskaya.android.data.Settings
import app.pushkinskaya.android.notify.Notifications
import app.pushkinskaya.android.notify.StatusCheckScheduler
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import java.util.concurrent.TimeUnit

class PushkinskayaApp : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
        Notifications.createChannels(this)
        StatusCheckScheduler.schedule(this)
    }
}

/** Plain constructor injection: no DI framework needed at this size. */
class AppContainer(context: Context) {
    val baseUrl: String = BuildConfig.API_BASE_URL

    private val json = Json { ignoreUnknownKeys = true }
    private val http = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)   // /predict can be slow on a cold server
        .build()

    val api: Api = Retrofit.Builder()
        .baseUrl(baseUrl)
        .client(http)
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()
        .create(Api::class.java)

    private val db = Room.databaseBuilder(context, AppDatabase::class.java, "pushkinskaya.db")
        // Both tables are a cache of server data (visit list included), so on a
        // schema change it is cheaper to refetch than to ship a migration.
        .fallbackToDestructiveMigration()
        .build()

    val settings = Settings(context)
    val landmarks = LandmarkRepository(api, db.landmarkDao(), db.routeDao())
    val routes = RouteRepository(api, db.routeDao())
    val identify = IdentifyRepository(api, context.applicationContext)

    fun photoUrl(landmarkId: String): String = "${baseUrl}photo/$landmarkId"
}

