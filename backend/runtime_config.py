import os
from urllib.parse import parse_qsl, urlsplit

from psycopg.conninfo import conninfo_to_dict


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
    bounded_integer(environ, "GITSCOPE_GITHUB_METADATA_GLOBAL_LIMIT_PER_MINUTE", 60, 1, 100000)
    if not str(environ.get("GITSCOPE_GITHUB_UPSTREAM_BUDGET_PER_HOUR", "")).strip():
        raise RuntimeError("GITSCOPE_GITHUB_UPSTREAM_BUDGET_PER_HOUR must be set in production")
    budget_default, budget_maximum, _ = github_upstream_budget_profile(environ)
    bounded_integer(
        environ,
        "GITSCOPE_GITHUB_UPSTREAM_BUDGET_PER_HOUR",
        budget_default,
        1,
        budget_maximum,
    )
    _validate_rate_limit_database_url(
        environ.get("GITSCOPE_RATE_LIMIT_DATABASE_URL", "")
    )


def _validate_rate_limit_database_url(connection_url):
    """Validate the same conninfo that psycopg will pass to libpq.

    Duplicate query keys are rejected before asking libpq to interpret them;
    this avoids relying on parser-specific precedence for a security option.
    The URL is validated in place and is never rewritten.
    """
    if not isinstance(connection_url, str) or not connection_url.strip():
        raise RuntimeError("GITSCOPE_RATE_LIMIT_DATABASE_URL must be a PostgreSQL connection URL")

    connection_url = connection_url.strip()
    try:
        parsed_url = urlsplit(connection_url)
        # Accessing .port validates that a provided port is syntactically valid.
        port = parsed_url.port
        query_options = parse_qsl(parsed_url.query, keep_blank_values=True, strict_parsing=True)
        sslmode_values = [value for key, value in query_options if key.lower() == "sslmode"]
        # Use psycopg's libpq parser to validate the actual URI syntax/options
        # which the connection pool will use below.
        driver_options = conninfo_to_dict(connection_url)
    except Exception:
        raise RuntimeError("GITSCOPE_RATE_LIMIT_DATABASE_URL is malformed or unsupported") from None

    if (
        parsed_url.scheme not in {"postgres", "postgresql"}
        or not parsed_url.hostname
        or not parsed_url.username
        or not parsed_url.password
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise RuntimeError("GITSCOPE_RATE_LIMIT_DATABASE_URL must be a PostgreSQL connection URL")

    if len(sslmode_values) != 1:
        raise RuntimeError("GITSCOPE_RATE_LIMIT_DATABASE_URL must contain exactly one sslmode")

    # Confirm the effective value from the same libpq parser used by psycopg.
    # Exact single-key validation above prevents URI duplicate-key precedence
    # from changing this security decision.
    if driver_options.get("sslmode", "").lower() not in {"require", "verify-ca", "verify-full"}:
        raise RuntimeError("GITSCOPE_RATE_LIMIT_DATABASE_URL must require TLS")


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


def github_upstream_budget_profile(environ=None):
    """Return a conservative hourly cap profile for the configured auth mode.

    Typical authenticated-user credentials have a 5,000 request/hour core
    quota. The default reserves most of that quota for other uses of the same
    credential, and the maximum reserves at least half. Less identifiable
    bearer credentials use a lower ceiling because app and Actions quotas can
    differ. Unauthenticated REST access is limited to 60/hour.

    Token contents are inspected only to select a profile and are never
    returned, logged, or included in validation errors.
    """
    environ = os.environ if environ is None else environ
    token = str(environ.get("GITHUB_TOKEN", "")).strip()
    if not token:
        return 20, 30, "unauthenticated"

    if token.startswith(("ghp_", "github_pat_", "gho_", "ghu_")):
        return 2000, 2500, "authenticated_user"

    # Installation and unrecognized bearer credentials can have different
    # limits (including per-repository Actions quotas), so use a lower cap
    # until the operator verifies the actual /rate_limit headers.
    return 200, 400, "other_bearer"


def cors_origins(environ=None):
    environ = os.environ if environ is None else environ
    configured = environ.get("GITSCOPE_CORS_ORIGINS")
    if configured is None:
        configured = "" if is_production(environ) else _LOCAL_CORS_ORIGINS
    return [origin.strip() for origin in configured.split(",") if origin.strip()]
