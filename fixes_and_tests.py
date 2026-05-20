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


if __name__ == "__main__":
    print("Run: pytest test_orchestration.py -v")
