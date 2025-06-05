import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.main import app


@pytest.fixture
def client() -> TestClient:
    """
    Create a test client for the FastAPI application.
    """
    return TestClient(app)


@pytest.fixture
def test_app() -> FastAPI:
    """
    Create a test instance of the FastAPI application.
    """
    return app
