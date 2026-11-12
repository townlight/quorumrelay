"""Fixed documented account API origins with application-owned namespace binding."""

import json
from urllib.parse import urlsplit

ORIGINS = {"municode-meetings": "https://meetingsgov.devmunicode.com",
           "telvue": "https://connect.telvue.com"}


def is_account_api(source):
    origin = ORIGINS.get(source.provider)
    return origin is not None and urlsplit(source.url).netloc == urlsplit(origin).netloc


def account_namespace(source):
    parsed = urlsplit(source.url)
    if (not is_account_api(source) or parsed.scheme != "https" or parsed.query or parsed.fragment
            or parsed.username or parsed.password or parsed.port is not None):
        raise ValueError("Use the exact documented HTTPS account API origin without query credentials.")
    if not source.namespace or len(source.namespace) > 512:
        raise ValueError("Account APIs require an explicit application-configured account namespace.")
    return source.namespace


def credentials(source, context):
    namespace = account_namespace(source)
    config = context.credentials.get(source.provider)
    allowed = config.get("allowed_namespaces", [config.get("namespace")]) if isinstance(config, dict) else None
    if (not isinstance(config, dict) or not context.tenant or config.get("tenant") != context.tenant
            or config.get("origin") != ORIGINS[source.provider]
            or not isinstance(allowed, (list, tuple)) or namespace not in allowed
            or (context.allowed_namespaces is not None and namespace not in context.allowed_namespaces)):
        raise ValueError("Trusted account credentials must bind the exact origin, caller tenant and namespace.")
    keys = ("token",) if source.provider == "municode-meetings" else ("access_key", "secret_passphrase")
    if any(not isinstance(config.get(key), str) or not config[key] or
           any(c in config[key] for c in "\r\n\0") for key in keys):
        raise ValueError("Trusted account credentials are missing or invalid.")
    return config


def headers(source, context):
    config = credentials(source, context)
    if source.provider == "municode-meetings":
        return {"Accept": "application/json", "Authorization": "Bearer " + config["token"]}
    return {"Accept": "application/json", "CONNECT-ACCESS-KEY": config["access_key"],
            "CONNECT-SECRET-PASSPHRASE": config["secret_passphrase"]}


def reject_credential_echo(content, config):
    # JSON escaping must not conceal an echoed secret inside an otherwise exact capture.
    try:
        decoded = json.dumps(json.loads(content), ensure_ascii=False).encode()
    except (ValueError, UnicodeError):
        decoded = content
    for key in ("token", "access_key", "secret_passphrase"):
        value = config.get(key)
        if isinstance(value, str) and value and (value.encode() in content or value.encode() in decoded):
            raise ValueError("A response containing credential material cannot be captured.")
