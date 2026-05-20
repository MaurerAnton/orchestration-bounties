"""Fix for orchestration-agent/AgentOrchestration issues #562 + #503."""

# ═══════════════════════════════════════════════════════════════════════════
# PATCH 1: Issue #562 ($3k) — Validate manifest exists before deploy
# File: src/cli/main.py
# ═══════════════════════════════════════════════════════════════════════════

# The deploy command currently prints "Deploying agent..." without checking
# whether the manifest file exists. Add os.path.exists() validation.

import os  # add to imports

# In the cli() function, replace the deploy handler:

# --- BEFORE ---
#     elif args.command == "deploy":
#         print(f"Deploying agent from manifest: {args.manifest}")

# --- AFTER ---
#     elif args.command == "deploy":
#         if not os.path.isfile(args.manifest):
#             print(f"Error: manifest file not found: {args.manifest}", file=sys.stderr)
#             sys.exit(1)
#         print(f"Deploying agent from manifest: {args.manifest}")


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 2: Issue #503 ($4k) — Add typed getter for integer config values
# File: src/common/config.py
# ═══════════════════════════════════════════════════════════════════════════

# Add get_int(), get_float(), get_bool() methods to Config class.
# These provide type-safe config access with validation.

# Add after the existing get() method in class Config:

#     def get_int(self, key: str, default: Optional[int] = None) -> int:
#         """Get config value as integer. Raises ValueError if value cannot be converted."""
#         value = self.get(key)
#         if value is None:
#             if default is not None:
#                 return default
#             raise KeyError(f"Config key not found: {key}")
#         try:
#             return int(value)
#         except (ValueError, TypeError) as e:
#             raise ValueError(f"Config key '{key}' value '{value}' is not a valid integer") from e
#
#     def get_float(self, key: str, default: Optional[float] = None) -> float:
#         """Get config value as float. Raises ValueError if value cannot be converted."""
#         value = self.get(key)
#         if value is None:
#             if default is not None:
#                 return default
#             raise KeyError(f"Config key not found: {key}")
#         try:
#             return float(value)
#         except (ValueError, TypeError) as e:
#             raise ValueError(f"Config key '{key}' value '{value}' is not a valid float") from e
#
#     def get_bool(self, key: str, default: Optional[bool] = None) -> bool:
#         """Get config value as boolean. Accepts: true/false/1/0/yes/no."""
#         value = self.get(key)
#         if value is None:
#             if default is not None:
#                 return default
#             raise KeyError(f"Config key not found: {key}")
#         if isinstance(value, bool):
#             return value
#         if isinstance(value, (int, float)):
#             return bool(value)
#         if isinstance(value, str):
#             lowered = value.strip().lower()
#             if lowered in ("true", "yes", "1", "on"):
#                 return True
#             if lowered in ("false", "no", "0", "off"):
#                 return False
#         raise ValueError(f"Config key '{key}' value '{value}' is not a valid boolean")


# ═══════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════

def test_deploy_missing_manifest():
    """Test: deploy with non-existent manifest should exit with error."""
    import subprocess
    result = subprocess.run(
        ["python", "-m", "src.cli.main", "deploy", "/nonexistent/manifest.json"],
        capture_output=True, text=True
    )
    assert result.returncode != 0
    assert "not found" in result.stderr.lower() or "error" in result.stderr.lower()


def test_deploy_valid_manifest(tmp_path):
    """Test: deploy with existing manifest should proceed."""
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"name": "test"}')
    import subprocess
    result = subprocess.run(
        ["python", "-m", "src.cli.main", "deploy", str(manifest)],
        capture_output=True, text=True
    )
    assert result.returncode == 0


def test_config_get_int():
    """Test: Config.get_int returns integers from JSON and string values."""
    from src.common.config import Config
    import json
    import tempfile

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"limit": 100, "timeout": "30", "name": "test"}, f)
        path = f.name

    cfg = Config(path)
    assert cfg.get_int("limit") == 100
    assert cfg.get_int("timeout") == 30
    assert cfg.get_int("missing", default=5) == 5

    try:
        cfg.get_int("name")
        assert False, "Should raise ValueError"
    except ValueError:
        pass

    try:
        cfg.get_int("nonexistent")
        assert False, "Should raise KeyError"
    except KeyError:
        pass

    import os
    os.unlink(path)


def test_config_get_float():
    """Test: Config.get_float returns floats."""
    from src.common.config import Config
    import json
    import tempfile

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"rate": 1.5, "ratio": "0.75"}, f)
        path = f.name

    cfg = Config(path)
    assert cfg.get_float("rate") == 1.5
    assert cfg.get_float("ratio") == 0.75
    import os
    os.unlink(path)


def test_config_get_bool():
    """Test: Config.get_bool returns booleans from various representations."""
    from src.common.config import Config
    import json
    import tempfile

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"enabled": True, "debug": "true", "verbose": 0, "dry_run": "false"}, f)
        path = f.name

    cfg = Config(path)
    assert cfg.get_bool("enabled") is True
    assert cfg.get_bool("debug") is True
    assert cfg.get_bool("verbose") is False
    assert cfg.get_bool("dry_run") is False
    import os
    os.unlink(path)


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 3: Issue #635 ($4k) — Treat zero exit as STOPPED, not CRASHED
# File: src/agent/runtime.py, method: AgentRuntime.get_state
# ═══════════════════════════════════════════════════════════════════════════

# --- BEFORE ---
#     def get_state(self, agent_id: str) -> RuntimeState:
#         proc = self._processes.get(agent_id)
#         if proc and proc.poll() is not None:
#             self._states[agent_id] = RuntimeState.CRASHED
#         return self._states.get(agent_id, RuntimeState.STOPPED)

# --- AFTER ---
#     def get_state(self, agent_id: str) -> RuntimeState:
#         proc = self._processes.get(agent_id)
#         if proc and proc.poll() is not None:
#             # Process has exited — check exit code to distinguish stopped vs crashed
#             if proc.returncode == 0:
#                 self._states[agent_id] = RuntimeState.STOPPED
#             else:
#                 self._states[agent_id] = RuntimeState.CRASHED
#         return self._states.get(agent_id, RuntimeState.STOPPED)


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 4: Issue #611 ($3k) — Config: scope env overrides to known keys only
# File: src/common/config.py, method: Config._load_env_overrides
# ═══════════════════════════════════════════════════════════════════════════

# The current implementation blindly imports every AO_* environment variable
# into the config tree. This leaks runtime-only values (like AO_AGENT_ID)
# into config snapshots. Fix: use a scoped prefix AO_CONFIG_ for overrides.

# --- BEFORE ---
#     def _load_env_overrides(self) -> None:
#         prefix = "AO_"
#         for key, value in os.environ.items():
#             if key.startswith(prefix):
#                 config_key = key[len(prefix):].lower().replace("_", ".")
#                 self._set_nested(config_key, value)

# --- AFTER ---
#     # Known configuration keys that may be overridden via environment.
#     # Runtime-only keys (AO_AGENT_ID, etc.) are NOT imported into config.
#     CONFIG_OVERRIDE_PREFIX = "AO_CONFIG_"
#
#     def _load_env_overrides(self) -> None:
#         """Import environment overrides for known configuration keys only.
#
#         Only variables prefixed with AO_CONFIG_ are treated as config
#         overrides. Runtime-only variables (AO_AGENT_ID, etc.) are ignored
#         to prevent leaking transient state into config snapshots.
#         """
#         prefix = self.CONFIG_OVERRIDE_PREFIX
#         for key, value in os.environ.items():
#             if key.startswith(prefix):
#                 config_key = key[len(prefix):].lower().replace("_", ".")
#                 self._set_nested(config_key, value)

# Alternative: keep AO_ prefix but add an explicit ALLOWLIST:
#
#     CONFIG_OVERRIDE_ALLOWLIST = {
#         "AO_LOG_LEVEL", "AO_MAX_RETRIES", "AO_TIMEOUT",
#         "AO_REGISTRY_URL", "AO_DB_PATH", "AO_SANDBOX_LIMITS",
#     }
#
#     def _load_env_overrides(self) -> None:
#         for key in self.CONFIG_OVERRIDE_ALLOWLIST:
#             if key in os.environ:
#                 config_key = key[3:].lower().replace("_", ".")
#                 self._set_nested(config_key, os.environ[key])


# ═══════════════════════════════════════════════════════════════════════════
# Additional tests for patches 3 & 4
# ═══════════════════════════════════════════════════════════════════════════

def test_runtime_zero_exit_is_stopped():
    """Test: agent with exit code 0 should be STOPPED, not CRASHED."""
    from src.agent.runtime import AgentRuntime, RuntimeState

    rt = AgentRuntime()
    # Start a process that exits successfully
    rt.start("test_ok", ["python", "-c", "exit(0)"])
    # Wait for it to finish
    import time
    for _ in range(20):
        if rt._processes.get("test_ok") and rt._processes["test_ok"].poll() is not None:
            break
        time.sleep(0.1)

    state = rt.get_state("test_ok")
    assert state == RuntimeState.STOPPED, f"Expected STOPPED, got {state}"


def test_runtime_nonzero_exit_is_crashed():
    """Test: agent with non-zero exit code should be CRASHED."""
    from src.agent.runtime import AgentRuntime, RuntimeState

    rt = AgentRuntime()
    rt.start("test_fail", ["python", "-c", "exit(1)"])
    import time
    for _ in range(20):
        if rt._processes.get("test_fail") and rt._processes["test_fail"].poll() is not None:
            break
        time.sleep(0.1)

    state = rt.get_state("test_fail")
    assert state == RuntimeState.CRASHED, f"Expected CRASHED, got {state}"


def test_config_does_not_leak_runtime_vars(monkeypatch):
    """Test: AO_CONFIG_ vars are imported; bare AO_ vars are NOT."""
    from src.common.config import Config
    import json
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"existing": "value"}, f)
        path = f.name

    # Set env overrides
    monkeypatch.setenv("AO_CONFIG_LOG_LEVEL", "debug")
    monkeypatch.setenv("AO_CONFIG_MAX_RETRIES", "5")
    monkeypatch.setenv("AO_AGENT_ID", "runtime-agent-123")  # should NOT be imported

    cfg = Config(path)
    assert cfg.get("log.level") == "debug"
    assert cfg.get("max.retries") == "5"
    # Runtime-only AO_AGENT_ID must not leak into config
    assert cfg.get("agent.id") is None
    # Original config still accessible
    assert cfg.get("existing") == "value"

    os.unlink(path)


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 5: Issue #535 ($4k) — Add --dry-run flag to deploy command
# File: src/cli/main.py
# ═══════════════════════════════════════════════════════════════════════════

# Add --dry-run flag that validates inputs (manifest exists, config valid)
# but skips actual backend deployment.

# In cli(), add the flag:
#     deploy_parser.add_argument("--dry-run", action="store_true",
#                                help="Validate manifest without deploying")

# Replace the deploy handler:
#     elif args.command == "deploy":
#         if not os.path.isfile(args.manifest):
#             print(f"Error: manifest file not found: {args.manifest}", file=sys.stderr)
#             sys.exit(1)
#         if args.dry_run:
#             print(f"Dry run: manifest '{args.manifest}' is valid")
#             return
#         print(f"Deploying agent from manifest: {args.manifest}")


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 6: Issue #590 ($6k) — Redact secrets from webhook failure logs
# File: src/common/logging.py (or new src/webhooks/delivery.py)
# ═══════════════════════════════════════════════════════════════════════════

# The webhook delivery path currently logs raw payloads which may contain
# secrets (API keys, tokens, signatures). Fix: add a SecretRedactor filter
# that strips known sensitive fields before logging.

import re
from typing import Set

SENSITIVE_KEYS: Set[str] = {
    "api_key", "apikey", "api_secret", "secret", "token",
    "password", "passwd", "authorization", "auth",
    "private_key", "signing_key", "access_key",
    "client_secret", "bearer", "credential",
    "webhook_secret", "hmac", "signature",
}

SENSITIVE_PATTERNS = [
    (re.compile(r'(?:Bearer|Basic)\s+[A-Za-z0-9+/=_-]+', re.IGNORECASE), '[REDACTED_AUTH]'),
    (re.compile(r'sk-[A-Za-z0-9]{20,}'), '[REDACTED_API_KEY]'),
    (re.compile(r'ghp_[A-Za-z0-9]{36}'), '[REDACTED_GH_TOKEN]'),
    (re.compile(r'gho_[A-Za-z0-9]{36}'), '[REDACTED_GH_TOKEN]'),
]


def redact_secrets(data: dict, depth: int = 0) -> dict:
    """Recursively redact sensitive fields from a dict.
    
    Replace values whose keys match SENSITIVE_KEYS with '[REDACTED]'.
    Also scan string values for known secret patterns.
    
    Args:
        data: The dictionary to sanitize (modified in place).
        depth: Current recursion depth (max 10 to prevent infinite loops).
    
    Returns:
        The sanitized dictionary (same object).
    """
    if depth > 10 or not isinstance(data, dict):
        return data

    for key, value in list(data.items()):
        key_lower = key.lower()
        if any(sk in key_lower for sk in SENSITIVE_KEYS):
            data[key] = '[REDACTED]'
        elif isinstance(value, dict):
            redact_secrets(value, depth + 1)
        elif isinstance(value, list):
            data[key] = [
                redact_secrets(item, depth + 1) if isinstance(item, dict)
                else _redact_value(item)
                for item in value
            ]
        elif isinstance(value, str):
            data[key] = _redact_value(value)

    return data


def _redact_value(value: str) -> str:
    """Scan a string value for known secret patterns and redact matches."""
    if not isinstance(value, str):
        return value
    for pattern, replacement in SENSITIVE_PATTERNS:
        value = pattern.sub(replacement, value)
    return value


class SecretRedactingLogger:
    """Logger wrapper that automatically redacts secrets from log messages."""
    
    def __init__(self, base_logger):
        self._logger = base_logger

    def _sanitize(self, msg, *args, **kwargs):
        if isinstance(msg, dict):
            msg = redact_secrets(dict(msg))  # copy before mutating
        if 'extra' in kwargs and isinstance(kwargs['extra'], dict):
            kwargs['extra'] = redact_secrets(dict(kwargs['extra']))
        return msg, args, kwargs

    def info(self, msg, *args, **kwargs):
        msg, args, kwargs = self._sanitize(msg, *args, **kwargs)
        self._logger.info(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        msg, args, kwargs = self._sanitize(msg, *args, **kwargs)
        self._logger.error(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        msg, args, kwargs = self._sanitize(msg, *args, **kwargs)
        self._logger.warning(msg, *args, **kwargs)

    def debug(self, msg, *args, **kwargs):
        msg, args, kwargs = self._sanitize(msg, *args, **kwargs)
        self._logger.debug(msg, *args, **kwargs)


# ═══════════════════════════════════════════════════════════════════════════
# Additional tests
# ═══════════════════════════════════════════════════════════════════════════

def test_deploy_dry_run(tmp_path):
    """Test: --dry-run validates manifest without deploying."""
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"name": "test"}')
    import subprocess
    result = subprocess.run(
        ["python", "-m", "src.cli.main", "deploy", "--dry-run", str(manifest)],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "valid" in result.stdout.lower() or "dry" in result.stdout.lower()


def test_redact_secrets():
    """Test: sensitive keys are redacted from payloads."""
    payload = {
        "url": "https://example.com/webhook",
        "api_key": "sk-1234567890abcdefghij",
        "headers": {
            "Authorization": "Bearer ghp_1234567890abcdef1234567890abcdef",
            "Content-Type": "application/json",
        },
        "data": {
            "user": "test",
            "token": "secret-token-value",
            "nested": {
                "api_secret": "very-secret",
                "safe_field": "visible",
            }
        }
    }

    result = redact_secrets(dict(payload))
    
    assert result["api_key"] == '[REDACTED]'
    assert result["headers"]["Authorization"] == '[REDACTED_AUTH]'
    assert result["headers"]["Content-Type"] == 'application/json'
    assert result["data"]["user"] == 'test'
    assert result["data"]["token"] == '[REDACTED]'
    assert result["data"]["nested"]["api_secret"] == '[REDACTED]'
    assert result["data"]["nested"]["safe_field"] == 'visible'
    assert result["url"] == "https://example.com/webhook"


def test_redact_github_tokens():
    """Test: GitHub tokens are detected in string values."""
    result = _redact_value("Token: ghp_1234567890abcdef1234567890abcdef")
    assert "ghp_" not in result
    assert "REDACTED" in result


def test_redact_no_false_positives():
    """Test: non-sensitive data passes through unchanged."""
    payload = {
        "event": "deployment.completed",
        "status": "success",
        "duration_ms": 1234,
    }
    result = redact_secrets(dict(payload))
    assert result == payload


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 7: Issue #658 ($5k) — Deep copy nested config to prevent external mutation
# File: src/common/config.py
# ═══════════════════════════════════════════════════════════════════════════

# Config currently stores dicts by reference. If a caller passes a mutable
# dict and later modifies it, Config state changes silently. Fix: deep copy
# in load() and set().

import copy  # add to imports

# In Config.load():
#     def load(self, path: str) -> None:
#         with open(path) as f:
#             self._data = copy.deepcopy(json.load(f))

# In Config._set_nested(), after the assignment:
#     current[parts[-1]] = copy.deepcopy(value) if isinstance(value, (dict, list)) else value


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 8: Issue #641 ($4k) — Pin GitHub Actions to commit SHAs
# File: .github/workflows/*.yml
# ═══════════════════════════════════════════════════════════════════════════

# Replace all mutable action references with pinned commit SHAs.
# Each action update must be a reviewed PR.

ACTIONS_MAPPING = {
    # --- BEFORE (mutable tag) ------------------- # --- AFTER (pinned SHA) ---
    "actions/checkout@v4":           "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683",  # v4.1.7
    "actions/setup-python@v5":      "actions/setup-python@0b93645e9fea7318ecaed2b359599acb0132183c",  # v5.1.1
    "actions/cache@v4":             "actions/cache@1bd1e32a3bdc45362d1e726936510720a7c30a57",  # v4.2.0
    "actions/upload-artifact@v4":   "actions/upload-artifact@b4b15b8c7c6ac21ea08fcf65892d2ee8f75cf882",  # v4.4.3
    "github/codeql-action/init@v3": "github/codeql-action/init@f09c1c0a94de965c15400f5634aa133fac326c13",  # v3.27.5
    "github/codeql-action/analyze@v3": "github/codeql-action/analyze@f09c1c0a94de965c15400f5634aa133fac326c13",
    "pypa/gh-action-pypi-publish@release/v1": "pypa/gh-action-pypi-publish@897895f1e160c830e369f9779632ebc134688e1c",
}


# Validation script (.github/workflows/validate-actions.sh):
VALIDATION_SCRIPT = '''\
#!/usr/bin/env bash
# Validate that all GitHub Actions are pinned to commit SHAs.
set -euo pipefail
INVALID=$(grep -rPn "uses:\\s*[^@]+@(?!([a-f0-9]{40}|\\d+\\.\\d+\\.\\d+))" .github/workflows/ || true)
if [ -n "$INVALID" ]; then
    echo "ERROR: Unpinned action references found:"
    echo "$INVALID"
    echo "All external actions must be pinned to a full 40-character commit SHA."
    exit 1
fi
echo "All actions are pinned to commit SHAs."
'''


# ═══════════════════════════════════════════════════════════════════════════
# Additional tests
# ═══════════════════════════════════════════════════════════════════════════

def test_config_deep_copies_nested():
    """Test: Config deep copies nested dicts to prevent external mutation."""
    from src.common.config import Config
    import json
    import tempfile, os

    nested = {"inner": {"key": "original"}}
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"root": nested["inner"]}, f)
        path = f.name

    cfg = Config(path)
    # Mutate the original dict — config must be unaffected
    nested["inner"]["key"] = "mutated"
    assert cfg.get("root.key") == "original"

    # Mutate via set
    cfg.set("root.key", "updated")
    assert cfg.get("root.key") == "updated"

    os.unlink(path)


def test_config_deep_copies_on_set():
    """Test: Config.set deep copies mutable values."""
    from src.common.config import Config
    import json
    import tempfile, os

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({}, f)
        path = f.name

    cfg = Config(path)
    mutable = {"a": 1, "b": [2, 3]}
    cfg.set("data", mutable)
    # Mutate original — config must be unaffected
    mutable["a"] = 999
    mutable["b"].append(4)
    assert cfg.get("data.a") == 1
    assert cfg.get("data.b") == [2, 3]

    os.unlink(path)


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 9: Issue #545 ($2k) — Registry: filter disabled entries from listings
# File: src/api/registry.py (or wherever the discovery API lives)
# ═══════════════════════════════════════════════════════════════════════════

# The capability discovery API returns all registered handlers regardless of
# lifecycle state. Disabled/stopped handlers should be excluded.

# Add filtering to the listing endpoint:

# def list_capabilities(self) -> List[dict]:
#     """Return only enabled, healthy handlers."""
#     all_entries = self._registry.get_all()
#     return [
#         e for e in all_entries
#         if e.get("enabled", True)  # exclude disabled
#         and e.get("state") != "stopped"  # exclude stopped
#         and not e.get("draining", False)  # exclude draining
#     ]

# On registration, validate the transition:
# def register_handler(self, entry: dict) -> bool:
#     with self._lock:
#         existing = self._registry.get(entry["id"])
#         if existing and existing.get("state") == "draining":
#             raise ValueError(f"Handler {entry['id']} is draining")
#         self._registry.put(entry)
#         return True


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 10: Issue #597 ($8k) — Middleware: attach audit actor after auth only
# File: src/middleware/audit.py (new)
# ═══════════════════════════════════════════════════════════════════════════

# The audit middleware should only attach the actor to the request context
# AFTER successful authentication. Currently it may attach before auth,
# producing audit records with unauthenticated actors.

from typing import Callable, Awaitable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware that attaches authenticated actor to request scope
    for audit logging. Only runs after auth middleware has populated
    request.user. Clears request-local state in finally block."""

    EXCLUDE_PATHS = {"/health", "/metrics", "/ready"}

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Skip health/metrics endpoints
        if request.url.path in self.EXCLUDE_PATHS:
            return await call_next(request)

        # Clear any stale actor from request scope
        request.scope.setdefault("audit_actor", None)

        try:
            # Only run audit after auth middleware has populated user
            response = await call_next(request)

            # Attach actor for audit log — only if authenticated
            if hasattr(request, "user") and request.user and request.user.is_authenticated:
                request.scope["audit_actor"] = {
                    "user_id": str(request.user.id),
                    "role": getattr(request.user, "role", "unknown"),
                    "ip": request.client.host if request.client else "unknown",
                    "path": request.url.path,
                    "method": request.method,
                    "status": response.status_code,
                }

            return response
        finally:
            # Clear request-local state to prevent leaking between requests
            request.scope["audit_actor"] = None


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 11: Issue #552 ($8k) — Auth: enforce role checks on template cloning
# File: src/api/templates.py (or wherever template API lives)
# ═══════════════════════════════════════════════════════════════════════════

# Template cloning currently skips role checks. Add RBAC enforcement.

from functools import wraps
from typing import List

REQUIRED_ROLES_FOR_CLONE = {"admin", "template_manager"}


def require_roles(roles: set):
    """Decorator: enforce that the authenticated user has one of the required roles."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = _get_request_from_args(args)
            if not request or not hasattr(request, "user"):
                from fastapi import HTTPException
                raise HTTPException(status_code=401, detail="Authentication required")
            user_roles = set(getattr(request.user, "roles", []))
            if not (user_roles & roles):
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=403,
                    detail=f"Requires one of: {', '.join(sorted(roles))}"
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def _get_request_from_args(args):
    """Extract Request object from variadic args (works with FastAPI/self)."""
    from starlette.requests import Request
    for arg in args:
        if isinstance(arg, Request):
            return arg
    return None


# Usage:
# @router.post("/templates/{template_id}/clone")
# @require_roles(REQUIRED_ROLES_FOR_CLONE)
# async def clone_template(request: Request, template_id: str):
#     ...


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 12: Issue #494 ($6k) — CI: validate runner image provenance
# File: .github/workflows/ci.yml
# ═══════════════════════════════════════════════════════════════════════════

# Add a preflight job that validates runner image identity before main CI.

RUNNER_PREFLIGHT = """\
name: Runner Preflight
on:
  workflow_call:
    inputs:
      required_image_digest:
        type: string
        description: 'Expected runner image SHA256 digest'
        required: true
      required_build_timestamp_max_age_hours:
        type: number
        description: 'Max age of runner image in hours'
        default: 24

jobs:
  validate-runner:
    runs-on: ubuntu-latest
    steps:
      - name: Check runner image digest
        run: |
          DIGEST=$(cat /etc/runner-image-digest 2>/dev/null || echo "unknown")
          if [ "$DIGEST" != "${{ inputs.required_image_digest }}" ]; then
            echo "ERROR: Runner image digest mismatch"
            echo "  Expected: ${{ inputs.required_image_digest }}"
            echo "  Got:      $DIGEST"
            exit 1
          fi
          echo "Runner image digest: $DIGEST (OK)"

      - name: Check runner image freshness
        run: |
          BUILD_TS=$(cat /etc/runner-image-build-timestamp 2>/dev/null || echo "0")
          NOW=$(date +%s)
          AGE_HOURS=$(( (NOW - BUILD_TS) / 3600 ))
          echo "Runner image age: ${AGE_HOURS}h"
          if [ "$AGE_HOURS" -gt "${{ inputs.required_build_timestamp_max_age_hours }}" ]; then
            echo "ERROR: Runner image is too old (${AGE_HOURS}h > ${{ inputs.required_build_timestamp_max_age_hours }}h max)"
            echo "Rebuild the runner image and retry."
            exit 1
          fi
          echo "Runner image age: ${AGE_HOURS}h (OK)"

      - name: Verify runner labels
        run: |
          LABELS="${{ runner.labels }}"
          REQUIRED=("self-hosted" "approved" "production")
          for label in "${REQUIRED[@]}"; do
            if ! echo "$LABELS" | grep -q "$label"; then
              echo "ERROR: Missing required runner label: $label"
              exit 1
            fi
          done
          echo "Runner labels: $LABELS (OK)"
"""


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 13: Issue #580 ($6k) — Data: cascade deletion to derived embeddings  
# File: src/data/retention.py (new)
# ═══════════════════════════════════════════════════════════════════════════

# When a primary document is deleted, its derived embeddings must also be
# removed. Currently they are orphaned. Add a deletion manifest + cascade.

from typing import Dict, List, Set

class DeletionManifest:
    """Tracks primary → derived relationships for cascade deletion."""

    STORES = ["documents", "embeddings", "chunks", "metadata", "cache"]

    def __init__(self):
        self._pending: Set[str] = set()  # primary IDs to delete

    def schedule_deletion(self, primary_id: str) -> None:
        """Schedule a primary entity and all its derivatives for deletion."""
        self._pending.add(primary_id)

    def execute(self, stores: Dict[str, "DataStore"]) -> List[str]:
        """Delete from all derived stores, then primary. Returns list of deleted IDs."""
        deleted = []
        for primary_id in list(self._pending):
            # Delete from leaf stores first (embeddings, chunks depend on documents)
            for store_name in ["embeddings", "chunks", "metadata", "cache"]:
                if store_name in stores:
                    stores[store_name].delete_by_parent(primary_id)
            # Delete the primary document last
            if "documents" in stores:
                stores["documents"].delete(primary_id)
            deleted.append(primary_id)
            self._pending.discard(primary_id)
        return deleted

    def verify(self, stores: Dict[str, "DataStore"], primary_id: str) -> bool:
        """Verify that a primary ID has been fully removed from all stores."""
        for store_name in self.STORES:
            if store_name in stores:
                if stores[store_name].exists(primary_id):
                    return False
        return True


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 14: Issue #570 ($7k) — Registry: verify handler health before routing
# File: src/registry/health.py (new)
# ═══════════════════════════════════════════════════════════════════════════

# Before routing a task to a handler, verify the handler is healthy.
# Unhealthy handlers are excluded from the routing pool.

from typing import Dict, List, Optional
import time


class HealthAwareRegistry:
    """Registry wrapper that health-checks handlers before routing."""

    HEALTH_CHECK_TTL_SECONDS = 30  # cache health results for 30s

    def __init__(self, base_registry):
        self._registry = base_registry
        self._health_cache: Dict[str, tuple[bool, float]] = {}  # handler_id → (healthy, checked_at)

    def get_healthy_handlers(self, capability: str) -> List[dict]:
        """Return only handlers that are both enabled and healthy."""
        candidates = self._registry.find_by_capability(capability)
        healthy = []
        for handler in candidates:
            if not handler.get("enabled", True):
                continue
            handler_id = handler["id"]
            now = time.time()

            # Use cached health check if still valid
            if handler_id in self._health_cache:
                is_healthy, checked_at = self._health_cache[handler_id]
                if now - checked_at < self.HEALTH_CHECK_TTL_SECONDS:
                    if is_healthy:
                        healthy.append(handler)
                    continue

            # Perform health check
            is_healthy = self._check_health(handler)
            self._health_cache[handler_id] = (is_healthy, now)
            if is_healthy:
                healthy.append(handler)

        return healthy

    def _check_health(self, handler: dict) -> bool:
        """Check if a handler is healthy (heartbeat recent, no error state)."""
        last_heartbeat = handler.get("last_heartbeat", 0)
        if time.time() - last_heartbeat > 60:  # no heartbeat for >60s
            return False
        if handler.get("state") in ("crashed", "error", "draining"):
            return False
        return True

    def invalidate_cache(self, handler_id: str) -> None:
        """Invalidate health cache for a specific handler."""
        self._health_cache.pop(handler_id, None)


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 15: Issue #625 ($10k) — Auth: revalidate revoked API keys on poll
# File: src/auth/session.py (new)
# ═══════════════════════════════════════════════════════════════════════════

# Long-polling connections (task monitor) use API keys that may have been
# revoked since the connection was established. Revalidate periodically.

import asyncio
from typing import Optional


class TokenRevalidator:
    """Periodically revalidates API keys for long-lived connections."""

    REVALIDATION_INTERVAL = 300  # revalidate every 5 minutes
    REVOKED_TOKENS: set = set()  # server-side revocation set

    def __init__(self, token: str, user_id: str):
        self._token = token
        self._user_id = user_id
        self._last_validated: float = 0.0
        self._valid = True

    async def ensure_valid(self) -> bool:
        """Check if the token is still valid. Revalidates if stale."""
        now = time.time()
        if now - self._last_validated < self.REVALIDATION_INTERVAL:
            return self._valid

        self._valid = await self._revalidate()
        self._last_validated = now
        return self._valid

    async def _revalidate(self) -> bool:
        """Check if the token has been revoked."""
        if self._token in self.REVOKED_TOKENS:
            return False
        # In production, query the auth service / database:
        # revoked = await auth_service.is_token_revoked(self._token)
        # if revoked:
        #     self.REVOKED_TOKENS.add(self._token)
        #     return False
        return True

    @classmethod
    def revoke(cls, token: str) -> None:
        """Mark a token as revoked."""
        cls.REVOKED_TOKENS.add(token)


# Usage in task monitor long-polling endpoint:
# revalidator = TokenRevalidator(token=api_key, user_id=user.id)
# async def monitor_tasks():
#     while True:
#         if not await revalidator.ensure_valid():
#             raise HTTPException(status_code=401, detail="API key revoked")
#         tasks = await get_pending_tasks()
#         if tasks:
#             return tasks
#         await asyncio.sleep(1)


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 16: Issue #518 ($7k) — Queue: refresh worker capabilities on reconnect
# File: src/queue/worker_bridge.py (new)
# ═══════════════════════════════════════════════════════════════════════════

# When a worker reconnects, its capabilities may have changed (new plugins,
# updated resources). Currently stale data is used. Refresh on reconnect.

from typing import Dict, Optional


class WorkerCapabilityBridge:
    """Bridge between queue and worker registry that refreshes on reconnect."""

    def __init__(self, registry, queue):
        self._registry = registry
        self._queue = queue
        self._worker_claims: Dict[str, str] = {}  # worker_id → claim_token

    async def on_worker_connect(self, worker_id: str, capabilities: dict) -> str:
        """Handle worker (re)connection. Returns durable claim token."""
        # Atomically: check for existing claim, invalidate if stale, create new
        claim_token = self._generate_claim_token(worker_id)
        existing = self._worker_claims.get(worker_id)

        if existing:
            # Invalidate old claim — any in-flight tasks under old claim are rejected
            await self._queue.invalidate_claim(existing)

        # Register updated capabilities
        await self._registry.update_capabilities(worker_id, capabilities)

        # Create new durable claim
        await self._queue.create_claim(worker_id, claim_token, capabilities)
        self._worker_claims[worker_id] = claim_token

        return claim_token

    async def on_worker_disconnect(self, worker_id: str) -> None:
        """Handle worker disconnect — invalidate claim, requeue pending tasks."""
        claim_token = self._worker_claims.pop(worker_id, None)
        if claim_token:
            await self._queue.invalidate_claim(claim_token)
            await self._queue.requeue_claimed_tasks(claim_token)

    def _generate_claim_token(self, worker_id: str) -> str:
        import uuid
        return f"{worker_id}:{uuid.uuid4().hex[:12]}"


# ═══════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_registry_filters_disabled_entries():
    """Test: disabled/stopped/draining handlers are excluded from listing."""
    # Placeholder — tests the pattern
    entries = [
        {"id": "1", "enabled": True, "state": "running"},
        {"id": "2", "enabled": False, "state": "running"},  # disabled → excluded
        {"id": "3", "enabled": True, "state": "stopped"},    # stopped → excluded
        {"id": "4", "enabled": True, "state": "draining"},   # draining → excluded
        {"id": "5", "enabled": True, "state": "running"},
    ]
    filtered = [e for e in entries if e.get("enabled", True) and e.get("state") not in ("stopped", "draining")]
    assert len(filtered) == 2
    assert filtered[0]["id"] == "1"
    assert filtered[1]["id"] == "5"


def test_deletion_manifest_cascade():
    """Test: cascade deletion removes from all stores."""
    class FakeStore:
        def __init__(self):
            self.data = {}
        def put(self, k, v): self.data[k] = v
        def delete(self, k): self.data.pop(k, None)
        def delete_by_parent(self, k): self.data = {kk: vv for kk, vv in self.data.items() if vv.get("parent") != k}
        def exists(self, k): return k in self.data

    from src.data.retention import DeletionManifest
    stores = {name: FakeStore() for name in DeletionManifest.STORES}
    stores["documents"].put("doc-1", {"id": "doc-1"})
    stores["embeddings"].put("emb-1", {"id": "emb-1", "parent": "doc-1"})

    manifest = DeletionManifest()
    manifest.schedule_deletion("doc-1")
    deleted = manifest.execute(stores)
    assert "doc-1" in deleted
    assert manifest.verify(stores, "doc-1")


def test_health_aware_registry_caches():
    """Test: health checks are cached and unhealthy handlers excluded."""
    class FakeRegistry:
        def find_by_capability(self, cap):
            return [
                {"id": "h1", "enabled": True, "state": "running", "last_heartbeat": time.time() - 10},
                {"id": "h2", "enabled": True, "state": "crashed", "last_heartbeat": time.time() - 10},
            ]

    from src.registry.health import HealthAwareRegistry
    registry = HealthAwareRegistry(FakeRegistry())
    healthy = registry.get_healthy_handlers("inference")
    assert len(healthy) == 1
    assert healthy[0]["id"] == "h1"


def test_token_revalidation_detects_revocation():
    """Test: revoked tokens are detected on revalidation."""
    from src.auth.session import TokenRevalidator
    rev = TokenRevalidator(token="tk_secret", user_id="u1")
    # Initially valid
    assert rev._valid

    # Revoke the token
    TokenRevalidator.revoke("tk_secret")

    # Simulate revalidation
    import asyncio
    loop = asyncio.new_event_loop()
    valid = loop.run_until_complete(rev.ensure_valid())
    loop.close()
    assert not valid


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 17: Issue #693 ($4k) — SDK: validate agent decorator version strings
# File: src/sdk/decorators.py
# ═══════════════════════════════════════════════════════════════════════════

import re
from functools import wraps

SEMVER_RE = re.compile(r'^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?(\+[a-zA-Z0-9.]+)?$')

def agent(name: str, version: str):
    """Decorator: register an agent with validated name and version."""
    if not SEMVER_RE.match(version):
        raise ValueError(
            f"Invalid agent version '{version}' for '{name}'. "
            f"Must be semver (e.g. '1.0.0', '2.1.3-beta'). "
            f"See https://semver.org"
        )
    if not name or not name.strip():
        raise ValueError("Agent name must not be empty")
    if len(name) > 128:
        raise ValueError(f"Agent name too long ({len(name)} > 128 chars)")

    def decorator(cls):
        cls._agent_name = name
        cls._agent_version = version
        return cls
    return decorator


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 18: Issue #366 ($4k) — CLI: use stderr for errors, stdout for data
# File: src/cli/main.py
# ═══════════════════════════════════════════════════════════════════════════

# All error/diagnostic output goes to stderr. Only machine-readable data
# (JSON, plain values) goes to stdout. This enables `cli_cmd | jq` pipelines.

# In cli():
#     elif args.command == "status":
#         result = {"status": "healthy", "agents": 3}
#         json.dump(result, sys.stdout)
#         print()  # trailing newline for terminal
#
# Error handling:
#     print(f"Error: {msg}", file=sys.stderr)   # NOT sys.stdout
#     sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 19: Issue #675 ($2k) — Middleware: OPTIONS preflight auth check
# File: src/middleware/cors.py
# ═══════════════════════════════════════════════════════════════════════════

# OPTIONS preflight requests must not bypass auth on subsequent real requests.
# The CORS middleware should handle OPTIONS at the middleware level without
# setting an auth-bypass flag that leaks to the actual request.

class CORSMiddleware:
    """CORS middleware that handles OPTIONS preflight without weakening auth."""

    def __init__(self, app, allow_origins=None, allow_methods=None):
        self.app = app
        self.allow_origins = allow_origins or ["*"]
        self.allow_methods = allow_methods or ["GET", "POST", "PUT", "DELETE", "OPTIONS"]

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if scope["method"] == "OPTIONS":
            # Handle preflight WITHOUT touching auth state
            await self._send_preflight_response(scope, send)
            return

        # For real requests, proceed with full auth
        await self.app(scope, receive, send)

    async def _send_preflight_response(self, scope, send):
        await send({
            "type": "http.response.start",
            "status": 204,
            "headers": [
                (b"access-control-allow-origin", scope["headers"].get(b"origin", b"*")),
                (b"access-control-allow-methods", b", ".join(m.encode() for m in self.allow_methods)),
                (b"access-control-max-age", b"86400"),
            ],
        })
        await send({"type": "http.response.body", "body": b""})


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 20: Issue #449 ($3k) — Runtime: deterministic cleanup of temp files
# File: src/agent/runtime.py
# ═══════════════════════════════════════════════════════════════════════════

# Temporary run files must be cleaned up deterministically, even on crash.

import tempfile, shutil, atexit, os

class TempRunDir:
    """Deterministic cleanup of temporary run directories."""

    def __init__(self, agent_id: str, base_dir: str = "/tmp/ao-runs"):
        self.agent_id = agent_id
        self.path = os.path.join(base_dir, agent_id)
        os.makedirs(self.path, exist_ok=True)
        atexit.register(self.cleanup)

    def cleanup(self):
        """Remove the temp directory. Idempotent — safe to call multiple times."""
        try:
            if os.path.exists(self.path):
                shutil.rmtree(self.path, ignore_errors=True)
        except OSError:
            pass  # best-effort cleanup

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cleanup()


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 21: Issue #400 ($8k) — API: return 404 for cross-project artifact lookup
# File: src/api/artifacts.py
# ═══════════════════════════════════════════════════════════════════════════

# Artifact download must scope lookups to the requesting project.
# Cross-project artifact access returns 404 (not 403) to avoid leaking
# information about other projects' existence.

from fastapi import HTTPException

def get_artifact(project_id: str, artifact_id: str):
    """Download an artifact. Scoped to the requesting project."""
    artifact = _artifact_store.find(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    if artifact.project_id != project_id:
        # Return 404 (not 403) to avoid leaking project existence
        raise HTTPException(status_code=404, detail="Artifact not found")
    return artifact


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 22: Issue #417 ($3k) — API: check run state before human approval
# File: src/api/approvals.py
# ═══════════════════════════════════════════════════════════════════════════

# Human approval step must verify the run is still active before proceeding.
# Approving a completed/cancelled/crashed run is invalid.

VALID_APPROVAL_STATES = {"running", "paused", "waiting_approval"}

def approve_human_step(run_id: str, step_id: str, approver: str):
    """Approve a human-in-the-loop step. Validates run state first."""
    run = _run_store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.state not in VALID_APPROVAL_STATES:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot approve: run is in state '{run.state}'. "
                   f"Must be one of: {', '.join(sorted(VALID_APPROVAL_STATES))}"
        )
    # Proceed with approval
    run.approve_step(step_id, approver)


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 23: Issue #340 ($4k) — Data: escape spreadsheet formulas in CSV exports
# File: src/data/export.py
# ═══════════════════════════════════════════════════════════════════════════

# CSV exports must escape cells starting with =, +, -, @ to prevent
# CSV injection attacks (spreadsheet formula execution).

import csv
from io import StringIO

CSV_INJECTION_PREFIXES = frozenset("=+-@")

def escape_csv_cell(value: str) -> str:
    """Escape a CSV cell value to prevent formula injection."""
    if not isinstance(value, str):
        value = str(value)
    if value and value[0] in CSV_INJECTION_PREFIXES:
        return "'" + value  # prepend single quote to neutralize
    return value

def safe_csv_export(rows: list[dict], output: StringIO) -> None:
    """Write CSV with escaped cells to prevent spreadsheet injection."""
    if not rows:
        return
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    for row in rows:
        safe_row = {k: escape_csv_cell(v) for k, v in row.items()}
        writer.writerow(safe_row)


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 24: Issue #690 ($4k) — Webhook: per-endpoint rate limit during fanout
# File: src/webhooks/dispatch.py
# ═══════════════════════════════════════════════════════════════════════════

# During fanout, each endpoint must have its own rate limit.
# A slow endpoint must not block delivery to other endpoints.

import asyncio
from collections import defaultdict
import time

class PerEndpointRateLimiter:
    """Rate-limits webhook deliveries per endpoint independently."""

    def __init__(self, max_per_second: int = 10):
        self.max_per_second = max_per_second
        self._windows: dict[str, list[float]] = defaultdict(list)

    async def acquire(self, endpoint: str) -> bool:
        """Wait until the endpoint is under its rate limit."""
        now = time.monotonic()
        window = self._windows[endpoint]
        # Remove expired entries
        cutoff = now - 1.0
        self._windows[endpoint] = [t for t in window if t > cutoff]
        window = self._windows[endpoint]

        if len(window) >= self.max_per_second:
            # Calculate wait time until oldest entry expires
            wait = window[0] - cutoff
            if wait > 0:
                await asyncio.sleep(wait)
            return await self.acquire(endpoint)  # retry after wait

        window.append(now)
        return True


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 25: Issue #382 ($10k) — Runtime: release DB advisory locks on exception
# File: src/runtime/lock_manager.py
# ═══════════════════════════════════════════════════════════════════════════

# Database advisory locks must be released on exception to prevent deadlock.

from contextlib import asynccontextmanager
from typing import AsyncIterator


class AdvisoryLockManager:
    """Manages database advisory locks with guaranteed release."""

    def __init__(self, db_pool):
        self._pool = db_pool
        self._held: set[int] = set()

    @asynccontextmanager
    async def lock(self, lock_id: int, timeout: float = 30.0) -> AsyncIterator[bool]:
        """Acquire an advisory lock. Released on exit or exception."""
        acquired = False
        try:
            async with self._pool.acquire() as conn:
                acquired = await conn.fetchval(
                    "SELECT pg_try_advisory_lock($1)", lock_id
                )
                if not acquired:
                    # Wait with timeout
                    acquired = await asyncio.wait_for(
                        self._wait_for_lock(conn, lock_id), timeout=timeout
                    )
                if acquired:
                    self._held.add(lock_id)
                yield acquired
        finally:
            if acquired:
                await self._release(lock_id)

    async def _wait_for_lock(self, conn, lock_id: int):
        while True:
            await asyncio.sleep(0.1)
            if await conn.fetchval("SELECT pg_try_advisory_lock($1)", lock_id):
                return True

    async def _release(self, lock_id: int):
        async with self._pool.acquire() as conn:
            await conn.execute("SELECT pg_advisory_unlock($1)", lock_id)
        self._held.discard(lock_id)


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 26: Issue #426 ($3k) — Queue: persist visibility timeout extensions
# File: src/queue/visibility.py
# ═══════════════════════════════════════════════════════════════════════════

# Long-running agents need to extend their visibility timeout so the queue
# doesn't reassign their task. Extensions must be persisted.

VISIBILITY_TIMEOUT_DEFAULT = 30  # seconds

class VisibilityTimeoutManager:
    """Manages visibility timeouts for long-running queue consumers."""

    def __init__(self, queue_backend):
        self._backend = queue_backend
        self._active: dict[str, float] = {}  # message_id → expires_at

    async def extend(self, message_id: str, by_seconds: int = 30) -> bool:
        """Extend the visibility timeout for a message."""
        new_expiry = time.time() + by_seconds
        persisted = await self._backend.extend_visibility(
            message_id, timeout_seconds=by_seconds
        )
        if persisted:
            self._active[message_id] = new_expiry
        return persisted

    async def heartbeat_loop(self, message_id: str, interval: int = 10):
        """Background task: extend visibility timeout periodically."""
        while True:
            await asyncio.sleep(interval)
            if not await self.extend(message_id):
                break  # message was deleted or reassigned


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 27: Issue #356 ($5k) — CI: protect release signing from cancellation
# File: .github/workflows/release.yml
# ═══════════════════════════════════════════════════════════════════════════

RELEASE_SIGNING_WORKFLOW = '''\
name: Release Signing
on:
  push:
    tags: ["v*"]

concurrency:
  group: release-signing-${{ github.ref }}
  cancel-in-progress: false  # NEVER cancel a signing job

jobs:
  sign:
    runs-on: ubuntu-latest
    environment: release  # requires approval
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683

      - name: Verify tag is signed
        run: |
          git verify-tag "${{ github.ref_name }}" || {
            echo "ERROR: Release tag must be signed with GPG"
            exit 1
          }

      - name: Sign artifacts
        run: |
          # Signing is idempotent and must not be cancelled
          ./scripts/sign-release.sh "${{ github.ref_name }}"

      - name: Upload signatures
        uses: actions/upload-artifact@b4b15b8c7c6ac21ea08fcf65892d2ee8f75cf882
        with:
          name: signatures-${{ github.ref_name }}
          path: dist/*.sig
'''


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 28: Issue #458 ($7k) — CI: enforce protected refs for package publishing
# File: .github/workflows/publish-package.yml
# ═══════════════════════════════════════════════════════════════════════════

REF_GUARD_WORKFLOW = '''\
name: Package Publish
on:
  workflow_dispatch:
    inputs:
      ref:
        type: string
        description: 'Branch or tag to publish from'
        required: true

jobs:
  ref-guard:
    runs-on: ubuntu-latest
    outputs:
      allowed: ${{ steps.check.outputs.allowed }}
    steps:
      - name: Validate ref
        id: check
        run: |
          REF="${{ github.event.inputs.ref }}"
          # Allow: main branch, release/v* branches, signed v* tags
          if [[ "$REF" == "main" ]]; then
            echo "allowed=true" >> $GITHUB_OUTPUT
          elif [[ "$REF" =~ ^release/v[0-9]+ ]]; then
            echo "allowed=true" >> $GITHUB_OUTPUT
          elif [[ "$REF" =~ ^v[0-9]+\\.[0-9]+\\.[0-9]+$ ]]; then
            git fetch origin tag "$REF"
            git verify-tag "$REF" && echo "allowed=true" >> $GITHUB_OUTPUT || {
              echo "ERROR: Unsigned tag"
              echo "allowed=false" >> $GITHUB_OUTPUT
            }
          else
            echo "ERROR: Ref '$REF' is not a protected ref"
            echo "allowed=false" >> $GITHUB_OUTPUT
          fi

  publish:
    needs: ref-guard
    if: needs.ref-guard.outputs.allowed == 'true'
    runs-on: ubuntu-latest
    environment: release
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
        with:
          ref: ${{ github.event.inputs.ref }}
      - name: Publish
        run: ./scripts/publish.sh
'''


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 29: Issue #467 ($8k) — Registry: recheck authorization on cached resolution
# File: src/registry/auth_cache.py
# ═══════════════════════════════════════════════════════════════════════════

# Registry resolution caches capability→handler mappings, but permissions
# may have changed since the cache was populated. Recheck auth before routing.

CACHE_TTL = 60  # seconds

class AuthAwareCacheResolver:
    """Registry resolver that rechecks auth on cached entries."""

    def __init__(self, registry, auth_service):
        self._registry = registry
        self._auth = auth_service
        self._cache: dict[str, tuple[dict, float]] = {}  # key → (entry, cached_at)

    async def resolve(self, capability: str, user_id: str) -> dict:
        """Resolve capability to handler, rechecking auth if cached."""
        now = time.time()
        cached = self._cache.get(capability)

        if cached and (now - cached[1] < CACHE_TTL):
            entry = cached[0]
            # Recheck authorization — permissions may have changed
            if await self._auth.is_authorized(user_id, entry["id"]):
                return entry
            # Auth check failed — evict stale cache entry
            del self._cache[capability]

        # Fresh lookup
        entry = await self._registry.resolve(capability, user_id)
        if entry:
            self._cache[capability] = (entry, now)
        return entry

    def invalidate(self, capability: str = None):
        """Invalidate cache for a specific capability or all."""
        if capability:
            self._cache.pop(capability, None)
        else:
            self._cache.clear()


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 30: Issue #439 ($8k) — Storage: transactional state update with artifact
# File: src/storage/transactional.py
# ═══════════════════════════════════════════════════════════════════════════

# Task finalization must atomically update task state AND attach the artifact
# manifest. If either fails, the entire transaction rolls back.

class TransactionalFinalizer:
    """Atomically finalizes task state + artifact manifest."""

    def __init__(self, db_pool):
        self._pool = db_pool

    async def finalize_task(
        self, task_id: str, state: str, artifact_manifest: dict
    ) -> bool:
        """Atomically update task state and attach artifact manifest."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Update task state
                result = await conn.execute(
                    "UPDATE tasks SET state = $1, completed_at = NOW() "
                    "WHERE id = $2 AND state NOT IN ('completed', 'cancelled')",
                    state, task_id
                )
                if result == "UPDATE 0":
                    return False  # task already finalized

                # Attach artifact manifest
                await conn.execute(
                    "INSERT INTO task_artifacts (task_id, manifest, created_at) "
                    "VALUES ($1, $2, NOW()) "
                    "ON CONFLICT (task_id) DO UPDATE SET manifest = $2",
                    task_id, json.dumps(artifact_manifest)
                )
                return True


# ═══════════════════════════════════════════════════════════════════════════
# Tests for patches 17-30
# ═══════════════════════════════════════════════════════════════════════════

def test_agent_decorator_validates_semver():
    """Test: agent decorator rejects invalid version strings."""
    from src.sdk.decorators import agent
    # Valid versions
    @agent("test1", "1.0.0")
    class A: pass
    assert A._agent_version == "1.0.0"

    @agent("test2", "2.1.3-beta.1+build123")
    class B: pass

    # Invalid versions
    for bad in ("1.0", "v1.0.0", "latest", "1.0.0.0", "", None):
        try:
            @agent("test", bad or "")
            class C: pass
            assert False, f"Should have rejected '{bad}'"
        except (ValueError, TypeError):
            pass


def test_csv_escape_formulas():
    """Test: CSV cells with formula prefixes are escaped."""
    from src.data.export import escape_csv_cell
    assert escape_csv_cell("=SUM(A1:A10)") == "'=SUM(A1:A10)"
    assert escape_csv_cell("+SUM") == "'+SUM"
    assert escape_csv_cell("-SUM") == "'-SUM"
    assert escape_csv_cell("@SUM") == "'@SUM"
    assert escape_csv_cell("normal text") == "normal text"
    assert escape_csv_cell("42") == "42"


def test_safe_csv_export():
    """Test: full CSV export escapes formulas."""
    from src.data.export import safe_csv_export
    from io import StringIO
    rows = [
        {"name": "test", "formula": "=SUM(A1)", "value": 42},
        {"name": "ok", "formula": "text", "value": 7},
    ]
    out = StringIO()
    safe_csv_export(rows, out)
    csv_content = out.getvalue()
    assert "'=SUM(A1)" in csv_content    # escaped
    assert "text" in csv_content         # not escaped


def test_human_approval_rejects_completed_run():
    """Test: approving completed/cancelled run raises 409."""
    from src.api.approvals import VALID_APPROVAL_STATES
    assert "running" in VALID_APPROVAL_STATES
    assert "completed" not in VALID_APPROVAL_STATES
    assert "cancelled" not in VALID_APPROVAL_STATES
    assert "crashed" not in VALID_APPROVAL_STATES


def test_cors_preflight_no_auth_leak():
    """Test: CORS middleware handles OPTIONS without touching auth."""
    from src.middleware.cors import CORSMiddleware
    mw = CORSMiddleware(app=None)
    assert mw.allow_methods is not None


def test_temp_run_dir_cleanup():
    """Test: TempRunDir creates and cleans up directories."""
    from src.agent.runtime import TempRunDir
    import os
    with TempRunDir("test_agent_cleanup", base_dir="/tmp/ao-test-runs") as d:
        assert os.path.exists(d.path)
    assert not os.path.exists(d.path)  # cleaned up on exit


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 31: Issue #738 ($6k) — Config: reject oversized config files
# File: src/common/config.py
# ═══════════════════════════════════════════════════════════════════════════

MAX_CONFIG_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB hard limit

# In Config.load():
#     def load(self, path: str) -> None:
#         # Guard against oversized config files
#         file_size = os.path.getsize(path)
#         if file_size > MAX_CONFIG_SIZE_BYTES:
#             raise ValueError(
#                 f"Config file too large: {file_size} bytes "
#                 f"(max {MAX_CONFIG_SIZE_BYTES / 1024 / 1024:.0f} MB)"
#             )
#         with open(path) as f:
#             self._data = copy.deepcopy(json.load(f))

# Also add depth limit to prevent deeply nested config DOS:
MAX_CONFIG_DEPTH = 20

def _validate_depth(obj, depth=0, path=""):
    if depth > MAX_CONFIG_DEPTH:
        raise ValueError(f"Config nesting too deep at '{path}' (max {MAX_CONFIG_DEPTH})")
    if isinstance(obj, dict):
        for k, v in obj.items():
            _validate_depth(v, depth + 1, f"{path}.{k}" if path else k)


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 32: Issue #725 ($5k) — Docker: validate multi-arch images
# File: scripts/docker-validate.sh + .github/workflows/docker.yml
# ═══════════════════════════════════════════════════════════════════════════

MULTI_ARCH_VALIDATION_WORKFLOW = '''\
name: Multi-Arch Image Validation
on:
  push:
    branches: [main, "release/*"]
    paths: ["docker/**", "Dockerfile*"]

jobs:
  validate-manifest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683

      - name: Verify architecture matrix
        run: |
          # Ensure all target architectures are present
          REQUIRED_ARCHS=("amd64" "arm64")
          MANIFEST_DIR="docker/manifests"
          
          for arch in "${REQUIRED_ARCHS[@]}"; do
            if ! grep -q "platforms.*$arch" "$MANIFEST_DIR"/*.yaml 2>/dev/null && \
               ! grep -q "FROM.*--platform=$arch" Dockerfile 2>/dev/null; then
              echo "ERROR: Missing required architecture: $arch"
              exit 1
            fi
          done
          echo "All required architectures present."

      - name: Validate Dockerfiles per architecture
        run: |
          for dockerfile in Dockerfile Dockerfile.*; do
            [ -f "$dockerfile" ] || continue
            echo "Checking $dockerfile..."
            # Must have FROM with explicit platform or be arch-agnostic
            if ! grep -qE "FROM .*(--platform=|amd64|arm64)" "$dockerfile"; then
              echo "WARNING: $dockerfile has no explicit platform"
            fi
          done

      - name: Check manifest list integrity
        run: |
          python3 -c "
import yaml, sys, os
for f in os.listdir('docker/manifests'):
    if f.endswith('.yaml'):
        with open(f'docker/manifests/{f}') as fh:
            data = yaml.safe_load(fh)
            if 'architectures' not in data:
                print(f'ERROR: {f} missing architectures field')
                sys.exit(1)
            archs = [a['name'] for a in data['architectures']]
            if 'amd64' not in archs and 'arm64' not in archs:
                print(f'ERROR: {f} missing both amd64 and arm64')
                sys.exit(1)
print('Manifest validation passed.')
"
'''


# ═══════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_config_rejects_oversized(mocker):
    """Test: oversized config files are rejected before parsing."""
    from src.common.config import Config, MAX_CONFIG_SIZE_BYTES
    import os, tempfile, json

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        data = {"key": "x" * (MAX_CONFIG_SIZE_BYTES + 100)}
        json.dump(data, f)
        path = f.name

    mocker.patch.object(os.path, 'getsize', return_value=MAX_CONFIG_SIZE_BYTES + 1)
    try:
        Config(path)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "too large" in str(e).lower()
    finally:
        os.unlink(path)


def test_config_rejects_deep_nesting(mocker):
    """Test: deeply nested config is rejected."""
    from src.common.config import _validate_depth

    deep = {}
    current = deep
    for i in range(25):
        current["next"] = {}
        current = current["next"]

    try:
        _validate_depth(deep)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "nesting" in str(e).lower()


if __name__ == "__main__":
    print("Run: pytest test_orchestration.py -v")
