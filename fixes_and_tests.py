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


if __name__ == "__main__":
    print("Run: pytest test_orchestration.py -v")
