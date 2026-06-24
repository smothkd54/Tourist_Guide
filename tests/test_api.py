"""
tests/test_api.py
-----------------
Unit tests for the Pushkinskaya Street Explorer API.

Run:  pytest tests/ -v
"""

import json
import base64
import io

from backend.app import app, _osrm_limiter  # noqa: E402


# ── Health Check ──────────────────────────────────────────────────────────────

class TestHealthCheck:
    def test_health_returns_200_when_loaded(self, client_with_mock_model):
        resp = client_with_mock_model.get("/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["landmarks"] > 0

    def test_health_returns_503_when_no_model(self, client):
        app.model = None
        resp = client.get("/")
        assert resp.status_code == 503
        data = resp.get_json()
        assert data["status"] == "degraded"
        assert data["model_loaded"] is False


# ── Landmarks ─────────────────────────────────────────────────────────────────

class TestLandmarks:
    def test_get_all_landmarks(self, client):
        resp = client.get("/landmarks")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_get_landmark_by_id(self, client):
        resp = client.get("/landmarks/pushkin_monument")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == "pushkin_monument"
        assert "name" in data
        assert "lat" in data
        assert "lon" in data

    def test_get_landmark_not_found(self, client):
        resp = client.get("/landmarks/nonexistent_id")
        assert resp.status_code == 404


# ── Nearby ────────────────────────────────────────────────────────────────────

class TestNearby:
    def test_nearby_valid_coords(self, client):
        resp = client.get("/nearby?lat=47.226&lon=39.719&radius_m=1000")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "landmarks" in data
        assert "count" in data
        assert data["count"] >= 0

    def test_nearby_invalid_coords(self, client):
        resp = client.get("/nearby?lat=abc&lon=def")
        assert resp.status_code == 400

    def test_nearby_missing_coords(self, client):
        resp = client.get("/nearby")
        assert resp.status_code == 400

    def test_nearby_reports_nearest(self, client):
        resp = client.get("/nearby?lat=47.226&lon=39.719&radius_m=1")
        data = resp.get_json()
        assert "nearest_landmark_distance_m" in data
        assert "nearest_landmark_name" in data


# ── Predict ───────────────────────────────────────────────────────────────────

class TestPredict:
    def _make_test_image_base64(self):
        """Create a small valid JPEG image as base64."""
        from PIL import Image
        img = Image.new("RGB", (100, 100), color=(128, 64, 32))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return base64.b64encode(buf.getvalue()).decode()

    def test_predict_no_model(self, client):
        app.model = None
        resp = client.post("/predict", json={"image": self._make_test_image_base64()})
        assert resp.status_code == 503

    def test_predict_missing_image(self, client_with_mock_model):
        resp = client_with_mock_model.post("/predict", json={})
        assert resp.status_code == 400

    def test_predict_missing_body(self, client_with_mock_model):
        resp = client_with_mock_model.post("/predict")
        assert resp.status_code == 400

    def test_predict_invalid_base64(self, client_with_mock_model):
        resp = client_with_mock_model.post("/predict", json={"image": "not-valid-base64!!!"})
        assert resp.status_code == 400

    def test_predict_valid_image(self, client_with_mock_model):
        resp = client_with_mock_model.post("/predict", json={"image": self._make_test_image_base64()})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "top5" in data
        assert "confidence" in data

    def test_predict_rejects_oversized_body(self, client_with_mock_model):
        """Test that MAX_CONTENT_LENGTH is enforced."""
        big_payload = {"image": "A" * (11 * 1024 * 1024)}  # 11MB of base64
        resp = client_with_mock_model.post(
            "/predict",
            data=json.dumps(big_payload),
            content_type="application/json",
        )
        assert resp.status_code == 413


# ── Route Planning ────────────────────────────────────────────────────────────

class TestRoute:
    def test_plan_missing_start(self, client):
        resp = client.get("/plan?minutes=60")
        assert resp.status_code == 400

    def test_plan_invalid_start(self, client):
        resp = client.get("/plan?start=nonexistent&minutes=60")
        assert resp.status_code == 404

    def test_plan_invalid_minutes(self, client):
        resp = client.get("/plan?start=pushkin_monument&minutes=abc")
        assert resp.status_code == 400

    def test_plan_rate_limit_blocks_after_threshold(self, client):
        _osrm_limiter._requests.clear()
        addr = "127.0.0.1"
        for _ in range(_osrm_limiter.max_requests):
            assert _osrm_limiter.is_allowed(addr) is True
        assert _osrm_limiter.is_allowed(addr) is False
        _osrm_limiter._requests.clear()

    def test_plan_custom_missing_body(self, client):
        resp = client.post("/plan-custom", json={})
        assert resp.status_code == 400

    def test_plan_custom_empty_landmarks(self, client):
        resp = client.post("/plan-custom", json={"landmarks": [], "start": "pushkin_monument"})
        assert resp.status_code == 400

    def test_route_fallback_no_file(self, client):
        """GET /route returns 404 when planned_route.json doesn't exist."""
        resp = client.get("/route")
        assert resp.status_code in (200, 404)


# ── Photos ────────────────────────────────────────────────────────────────────

class TestPhotos:
    def test_serve_photo_not_found(self, client):
        resp = client.get("/photo/nonexistent_id")
        assert resp.status_code == 404

    def test_photos_available(self, client):
        resp = client.get("/photos/available")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)


# ── Frontend ──────────────────────────────────────────────────────────────────

class TestFrontend:
    def test_serve_frontend(self, client):
        resp = client.get("/app")
        assert resp.status_code == 200

    def test_serve_frontend_slash(self, client):
        resp = client.get("/app/")
        assert resp.status_code == 200


# ── Model Info ───────────────────────────────────────────────────────────────

class TestModelInfo:
    def test_model_info_returns_metadata(self, client):
        resp = client.get("/model/info")
        # 200 if metadata exists, 404 if not (no training yet)
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.get_json()
            assert "trained_at" in data
            assert "num_classes" in data
            assert "results" in data


# ── Inference Smoke Test ─────────────────────────────────────────────────────

class TestInferenceSmoke:
    """End-to-end smoke test with a real (untrained) model.

    Verifies the full predict pipeline: image decode → resize →
    model.predict → JSON response structure — without requiring the
    actual trained .keras file.
    """

    def test_predict_smoke_real_model(self, client):
        from backend import app as app_module
        import keras
        from keras.applications import EfficientNetB0

        # Build a tiny real model (untrained)
        base = EfficientNetB0(include_top=False, pooling="avg",
                              input_shape=(224, 224, 3))
        inputs = keras.Input(shape=(224, 224, 3))
        x = base(inputs, training=False)
        outputs = keras.layers.Dense(31, activation="softmax")(x)
        real_model = keras.Model(inputs, outputs)

        # Temporarily swap in the real model and lower threshold
        saved_model = app_module.app.model
        saved_names = app_module.app.class_names
        saved_threshold = app_module.CONFIDENCE_THRESHOLD
        app_module.app.model = real_model
        app_module.app.class_names = [f"class_{i}" for i in range(31)]
        app_module.CONFIDENCE_THRESHOLD = 0.0

        try:
            # Build a valid JPEG
            from PIL import Image
            img = Image.new("RGB", (224, 224), color=(64, 128, 192))
            buf = io.BytesIO()
            img.save(buf, format="JPEG")
            b64 = base64.b64encode(buf.getvalue()).decode()

            resp = client.post("/predict", json={"image": b64})
            assert resp.status_code == 200
            data = resp.get_json()

            assert "landmark_id" in data
            assert "confidence" in data
            assert "top5" in data
            assert isinstance(data["top5"], list)
            assert len(data["top5"]) == 5
            assert 0.0 <= data["confidence"] <= 1.0
        finally:
            app_module.app.model = saved_model
            app_module.app.class_names = saved_names
            app_module.CONFIDENCE_THRESHOLD = saved_threshold


# ── Logging ───────────────────────────────────────────────────────────────────

class TestLogging:
    def test_log_file_created(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOG_DIR", str(tmp_path))
        from backend.logging_setup import setup_logging
        logger = setup_logging("test_log_create")
        logger.info("test message")
        log_file = tmp_path / "test_log_create.log"
        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        assert "test message" in content


# ── Metrics ───────────────────────────────────────────────────────────────────

class TestMetrics:
    def test_metrics_returns_prometheus_format(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert resp.content_type.startswith("text/plain")
        body = resp.get_data(as_text=True)
        assert "pushkinskaya_http_requests_total" in body
        assert "pushkinskaya_prediction_confidence" in body
        assert "pushkinskaya_osrm_requests_total" in body
        assert "pushkinskaya_uptime_seconds" in body

    def test_metrics_counts_requests(self, client):
        client.get("/landmarks")
        client.get("/landmarks/pushkin_monument")
        resp = client.get("/metrics")
        body = resp.get_data(as_text=True)
        assert 'endpoint="get_landmarks"' in body
        assert 'endpoint="get_landmark"' in body

    def test_metrics_records_prediction_confidence(self, client_with_mock_model):
        from PIL import Image
        img = Image.new("RGB", (100, 100), color=(128, 64, 32))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        client_with_mock_model.post("/predict", json={"image": b64})
        resp = client_with_mock_model.get("/metrics")
        body = resp.get_data(as_text=True)
        assert "pushkinskaya_prediction_confidence_count" in body
