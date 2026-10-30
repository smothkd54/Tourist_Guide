package app.pushkinskaya.android.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

/** Shapes below match the Flask API in backend/app.py (checked against its source). */
@Serializable
data class LandmarkDto(
    val id: String,
    val name: String,
    @SerialName("name_ru") val nameRu: String = "",
    val type: String = "",
    val lat: Double,
    val lon: Double,
    val address: String = "",
    val description: String = "",
    @SerialName("fun_fact") val funFact: String = "",
    @SerialName("year_built") val yearBuilt: Int? = null,
    val style: String = "",
    val architect: String = "",
    /** Not sent by the Flask API yet. The place-status badge and alerts need the server to add it. */
    val status: String? = null,
)

@Serializable
data class PredictRequest(val image: String)

@Serializable
data class Candidate(
    @SerialName("landmark_id") val landmarkId: String,
    val confidence: Double,
)

@Serializable
data class PredictResponse(
    val identified: Boolean,
    @SerialName("landmark_id") val landmarkId: String? = null,
    val name: String? = null,
    val confidence: Double = 0.0,
    val message: String? = null,
    val top5: List<Candidate> = emptyList(),
)

@Serializable
data class PlanRequest(
    val landmarks: List<String>,
    val start: String,
    val optimize: Boolean = true,
)

@Serializable
data class Stop(
    val id: String,
    val name: String,
    val lat: Double,
    val lon: Double,
    @SerialName("estimated_visit_minutes") val visitMinutes: Int,
)

@Serializable
data class PlanResponse(
    val stops: List<Stop>,
    @SerialName("total_walking_minutes") val walkingMinutes: Double,
    @SerialName("total_visit_minutes") val visitingMinutes: Double,
    @SerialName("total_minutes") val totalMinutes: Double,
)

interface Api {
    @GET("landmarks")
    suspend fun landmarks(): List<LandmarkDto>

    @POST("predict")
    suspend fun predict(@Body body: PredictRequest): PredictResponse

    @POST("plan-custom")
    suspend fun planCustom(@Body body: PlanRequest): PlanResponse
}
