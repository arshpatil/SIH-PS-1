import pytest
from app import create_app
from app.extensions import db


@pytest.fixture
def app():
    """Create and configure a testing instance of the Flask application."""
    test_app = create_app("testing")

    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Test client for issuing requests to the test application."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """CLI test runner for the test application."""
    return app.test_cli_runner()
