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

    bounded_integer(environ, "GITSCOPE_GITHUB_MAX_PAGES", 10, 1, 100)
    bounded_integer(environ, "GITSCOPE_ANALYSIS_TIMEOUT_SECONDS", 45, 5, 55)
    bounded_integer(environ, "GITSCOPE_GITHUB_MAX_FILE_FETCHES", 100, 1, 500)
    bounded_integer(environ, "GITSCOPE_PUBLIC_ANALYTICS_LIMIT_PER_MINUTE", 60, 1, 10000)


def bounded_integer(environ, name, default, minimum, maximum):
    environ = os.environ if environ is None else environ
    value = environ.get(name)
    try:
        parsed = default if value is None or not str(value).strip() else int(value)
    except (TypeError, ValueError):
        raise RuntimeError(f"{name} must be an integer between {minimum} and {maximum}") from None
    if not minimum <= parsed <= maximum:
        raise RuntimeError(f"{name} must be an integer between {minimum} and {maximum}")
    return parsed


def cors_origins(environ=None):
    environ = os.environ if environ is None else environ
    configured = environ.get("GITSCOPE_CORS_ORIGINS")
    if configured is None:
        configured = "" if is_production(environ) else _LOCAL_CORS_ORIGINS
    return [origin.strip() for origin in configured.split(",") if origin.strip()]
