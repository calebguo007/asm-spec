#!/usr/bin/env python3
"""Tests for ASM metadata embedded in MCP Registry server.json files."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_server_json_asm import PUBLISHER_META_KEY, inspect_server_json, validate_manifest


EXAMPLES = ROOT / "examples" / "mcp-server-json"


def test_valid_server_json_with_inline_asm_passes():
    result = inspect_server_json(EXAMPLES / "remote-with-asm.server.json")

    assert result.has_asm is True
    assert result.valid_asm is True
    assert result.can_convert is True
    assert result.asm_service_id == "example/remote-search@1.0"
    assert result.asm_taxonomy == "tool.data.search"
    assert result.missing_recommended_fields == []


def test_missing_asm_block_is_warning_not_error(tmp_path):
    server_json = tmp_path / "server.json"
    server_json.write_text(
        json.dumps({
            "name": "io.asm.example/no-asm",
            "description": "No ASM metadata yet",
            "_meta": {
                PUBLISHER_META_KEY: {
                    "maintainer": "example"
                }
            },
        }),
        encoding="utf-8",
    )

    result = inspect_server_json(server_json)

    assert result.has_asm is False
    assert result.valid_asm is False
    assert result.errors == []
    assert result.warnings


def test_malformed_asm_reports_schema_errors(tmp_path):
    server_json = tmp_path / "server.json"
    server_json.write_text(
        json.dumps({
            "name": "io.asm.example/bad-asm",
            "_meta": {
                PUBLISHER_META_KEY: {
                    "asm": {
                        "asm_version": "0.3",
                        "service_id": "example/bad@1.0"
                    }
                }
            },
        }),
        encoding="utf-8",
    )

    result = inspect_server_json(server_json)

    assert result.has_asm is True
    assert result.valid_asm is False
    assert result.can_convert is False
    assert any("taxonomy" in error for error in result.errors)


def test_extracted_manifest_validates_against_schema():
    result = inspect_server_json(EXAMPLES / "package-with-asm.server.json")

    assert result.asm_manifest is not None
    assert validate_manifest(result.asm_manifest) == []
    assert result.asm_manifest["service_id"] == "example/vector-db@1.0"
