import os


_LOCAL_CORS_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"


def is_production(environ=None):
    environ = os.environ if environ is None else environ
    return environ.get("GITSCOPE_ENV", "").strip().lower() == "production"


def _enabled(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def debug_enabled(environ=None):
    environ = os.environ if environ is None else environ
    configured = environ.get("FLASK_DEBUG")
    return not is_production(environ) and (configured is None or _enabled(configured))


def validate_runtime_config(environ=None):
    environ = os.environ if environ is None else environ
    if not is_production(environ):
        return

    if environ.get("GITSCOPE_CORS_ORIGINS", "").strip():
        raise RuntimeError("GITSCOPE_CORS_ORIGINS must be empty in production")
    if _enabled(environ.get("FLASK_DEBUG")):
        raise RuntimeError("FLASK_DEBUG must be disabled in production")


def cors_origins(environ=None):
    environ = os.environ if environ is None else environ
    configured = environ.get("GITSCOPE_CORS_ORIGINS")
    if configured is None:
        configured = "" if is_production(environ) else _LOCAL_CORS_ORIGINS
    return [origin.strip() for origin in configured.split(",") if origin.strip()]
