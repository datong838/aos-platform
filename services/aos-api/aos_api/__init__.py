from aos_api.logging_facade import configure_logging
from aos_api.main import app, create_app

configure_logging()

__all__ = ["app", "create_app"]
