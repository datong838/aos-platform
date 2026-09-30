from aos_api.logging_facade import configure_logging

configure_logging()

__all__ = ["app", "create_app"]


def __getattr__(name):
    # Standalone tools must not initialize the Web application on package import.
    if name in __all__:
        from aos_api.main import app, create_app
        globals().update(app=app, create_app=create_app)
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
