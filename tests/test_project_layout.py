from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION_DIR = ROOT / "custom_components" / "novastar_h"


def test_integration_files_exist() -> None:
    required = [
        INTEGRATION_DIR / "manifest.json",
        INTEGRATION_DIR / "__init__.py",
        INTEGRATION_DIR / "config_flow.py",
        INTEGRATION_DIR / "coordinator.py",
        INTEGRATION_DIR / "api.py",
        INTEGRATION_DIR / "switch.py",
        INTEGRATION_DIR / "select.py",
        INTEGRATION_DIR / "number.py",
        INTEGRATION_DIR / "media_player.py",
        ROOT / "README.md",
        ROOT / "hacs.json",
    ]
    for file_path in required:
        assert file_path.exists(), f"Missing required file: {file_path}"


def test_manifest_domain_is_correct() -> None:
    manifest_path = INTEGRATION_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["domain"] == "novastar_h"
    assert manifest["config_flow"] is True
    assert manifest["integration_type"] == "device"
    assert manifest["version"]
    assert manifest["documentation"].startswith("https://github.com/tedr91/HA-novastar-h")


def test_hacs_metadata_is_present() -> None:
    hacs_path = ROOT / "hacs.json"
    hacs = json.loads(hacs_path.read_text(encoding="utf-8"))

    assert "novastar_h" in hacs["domains"]
    assert hacs["content_in_root"] is False
