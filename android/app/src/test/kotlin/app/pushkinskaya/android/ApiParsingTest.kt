package app.pushkinskaya.android

import app.pushkinskaya.android.data.LandmarkDto
import app.pushkinskaya.android.data.PlanResponse
import app.pushkinskaya.android.data.PredictResponse
import app.pushkinskaya.android.data.isNotOpen
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Samples follow the field names in the Flask API (backend/app.py) and data/landmarks.json. */
class ApiParsingTest {
    private val json = Json { ignoreUnknownKeys = true }

    @Test
    fun `a landmark parses, ignores extra fields, and has no status yet`() {
        val text = """
            {"id":"pushkin_monument","name":"Monument to Alexander Pushkin","name_ru":"Памятник А.С. Пушкину",
             "type":"Monument","lat":47.22601,"lon":39.719028,"address":"Some street","description":"d",
             "fun_fact":"f","year_built":1959,"style":"s","architect":"a","angles":["front"],
             "photos":["https://example.com/a.jpg"],"coordinate_source":"manual (Yandex Maps)"}
        """.trimIndent()
        val landmark = json.decodeFromString<LandmarkDto>(text)
        assertEquals("pushkin_monument", landmark.id)
        assertEquals(1959, landmark.yearBuilt)
        assertEquals("Памятник А.С. Пушкину", landmark.nameRu)
        assertNull(landmark.status)
    }

    @Test
    fun `a confident prediction parses`() {
        val text = """
            {"identified":true,"landmark_id":"pushkin_monument","name":"Monument","confidence":0.82,
             "confidence_pct":"82.0%","top5":[{"landmark_id":"pushkin_monument","confidence":0.82}],"info":{}}
        """.trimIndent()
        val result = json.decodeFromString<PredictResponse>(text)
        assertTrue(result.identified)
        assertEquals("pushkin_monument", result.landmarkId)
        assertEquals(1, result.top5.size)
    }

    @Test
    fun `a low confidence prediction parses without a landmark`() {
        val text = """
            {"identified":false,"message":"Confidence too low.","confidence":0.06,
             "top5":[{"landmark_id":"a","confidence":0.06},{"landmark_id":"b","confidence":0.05}]}
        """.trimIndent()
        val result = json.decodeFromString<PredictResponse>(text)
        assertFalse(result.identified)
        assertNull(result.landmarkId)
        assertEquals(2, result.top5.size)
    }

    @Test
    fun `a route plan parses and ignores the geometry`() {
        val text = """
            {"stops":[{"id":"a","name":"A","lat":47.2,"lon":39.7,"estimated_visit_minutes":4}],
             "total_walking_minutes":0,"total_visit_minutes":4.0,"total_minutes":4.0,
             "route_geometry":{"type":"LineString","coordinates":[[39.7,47.2]]}}
        """.trimIndent()
        val plan = json.decodeFromString<PlanResponse>(text)
        assertEquals(1, plan.stops.size)
        assertEquals(4, plan.stops[0].visitMinutes)
        assertEquals(4.0, plan.totalMinutes, 0.0)
    }

    @Test
    fun `only closed values count as not open`() {
        assertTrue(isNotOpen("closed"))
        assertTrue(isNotOpen("temporarily_closed"))
        assertFalse(isNotOpen("open"))
        assertFalse(isNotOpen(null))
    }
}

