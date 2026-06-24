"""
tests/conftest.py
-----------------
Shared pytest fixtures for the Pushkinskaya Street Explorer test suite.
"""

from unittest.mock import MagicMock

import numpy as np
import pytest

from backend.app import app, load_resources


@pytest.fixture
def client():
    """Create a test client with landmarks loaded but no model."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        if not app.landmarks_by_id:
            load_resources()
        yield client


@pytest.fixture
def client_with_mock_model(client):
    """Create a test client with a mock model that returns random predictions."""
    mock_model = MagicMock()
    mock_model.predict.return_value = [np.random.dirichlet(np.ones(31))]
    app.model = mock_model
    yield client
    app.model = None
