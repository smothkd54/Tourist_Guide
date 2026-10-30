package app.pushkinskaya.android.data

import android.content.Context
import android.net.Uri
import app.pushkinskaya.android.util.ImageUtil
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.withContext

data class StatusChange(val id: String, val name: String, val status: String?)

private fun LandmarkDto.toEntity() = LandmarkEntity(
    id = id, name = name, nameRu = nameRu, type = type, lat = lat, lon = lon,
    address = address, description = description, funFact = funFact, yearBuilt = yearBuilt,
    style = style, architect = architect, status = status,
)

class LandmarkRepository(
    private val api: Api,
    private val dao: LandmarkDao,
    private val routeDao: RouteDao,
) {
    val landmarks: Flow<List<LandmarkEntity>> = dao.observeAll()

    fun landmark(id: String): Flow<LandmarkEntity?> = dao.observe(id)

    /**
     * Downloads the list and caches it. Returns the landmarks on the visit list whose status changed,
     * so a caller can show a notification. Offline, the cached list stays in use.
     */
    suspend fun refresh(): Result<List<StatusChange>> = runCatching {
        val before = dao.getAll().associate { it.id to it.status }
        val fresh = api.landmarks().map { it.toEntity() }
        dao.upsertAll(fresh)
        val onRoute = routeDao.getAll().map { it.landmarkId }.toSet()
        fresh
            .filter { it.id in onRoute && before.containsKey(it.id) && it.status != before[it.id] }
            .map { StatusChange(it.id, it.name, it.status) }
    }
}

class RouteRepository(
    private val api: Api,
    private val dao: RouteDao,
) {
    val items: Flow<List<RouteItemEntity>> = dao.observe()

    suspend fun add(landmarkId: String) = dao.add(RouteItemEntity(landmarkId, dao.nextPosition()))

    suspend fun remove(landmarkId: String) = dao.remove(landmarkId)

    suspend fun clear() = dao.clear()

    /** The first landmark in the list is the start point. */
    suspend fun plan(ids: List<String>, optimize: Boolean): Result<PlanResponse> = runCatching {
        api.planCustom(PlanRequest(landmarks = ids, start = ids.first(), optimize = optimize))
    }
}

class IdentifyRepository(
    private val api: Api,
    private val context: Context,
) {
    /** Resizes the photo on the phone (1024 px JPEG), then asks the server to identify it. */
    suspend fun identify(photo: Uri): Result<PredictResponse> = runCatching {
        val base64 = withContext(Dispatchers.Default) { ImageUtil.toJpegBase64(context, photo) }
        api.predict(PredictRequest(base64))
    }
}
