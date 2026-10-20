"""
tests/conftest.py
-----------------
Shared pytest fixtures for the Pushkinskaya Street Explorer test suite.
"""

from unittest.mock import MagicMock

import numpy as np
import pytest

from backend.app import app


@pytest.fixture
def client():
    """Test client. Resources load at backend.app import time, not per-test."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def client_with_mock_model(client):
    """Create a test client with a mock model that returns random predictions."""
    mock_model = MagicMock()
    mock_model.predict.return_value = [np.random.dirichlet(np.ones(31))]
    app.model = mock_model
    yield client
    app.model = None
