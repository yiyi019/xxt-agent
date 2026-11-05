# -*- coding: utf-8 -*-
"""Tests for the unified config location and legacy-file migration."""
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import xxt_agent.config as cfgmod
from xxt_agent.config import XXTConfig


class TestConfigPaths(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.new_dir = root / "home" / "xxt-agent"
        self.old_pkg = root / "pkg"
        self.old_pkg.mkdir()
        self.old_config = self.old_pkg / "config.json"
        self.old_cookies = self.old_pkg / "data" / "cookies.pkl"

        patches = [
            patch.object(cfgmod, "PACKAGE_DIR", self.old_pkg),
            patch.object(cfgmod, "DEFAULT_CONFIG_PATH", self.new_dir / "config.json"),
            patch.object(cfgmod, "DATA_DIR", self.new_dir / "data"),
            patch.object(cfgmod, "LEGACY_LOCATIONS", [self.old_config]),
            patch.object(cfgmod, "LEGACY_COOKIES_PATH", self.old_cookies),
            patch.object(cfgmod, "LEGACY_CONFIG_PATH", root / "nonexistent.json"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_default_paths_are_outside_package(self):
        self.assertNotIn(self.old_pkg, cfgmod.DEFAULT_CONFIG_PATH.parents)

    def test_load_without_any_file_returns_defaults_and_writes_nothing(self):
        cfg = XXTConfig.load()
        self.assertEqual(cfg.api_model, "deepseek-flash")
        self.assertFalse((self.new_dir / "config.json").exists())

    def test_legacy_config_and_cookies_are_migrated_once(self):
        self.old_config.write_text(
            json.dumps({
                "api_key": "sk-old",
                "speed": 2.0,
                "cookies_path": str(self.old_cookies),
            }),
            encoding="utf-8",
        )
        self.old_cookies.parent.mkdir(parents=True)
        self.old_cookies.write_bytes(b"cookie-bytes")

        cfg = XXTConfig.load()

        self.assertEqual(cfg.api_key, "sk-old")
        self.assertEqual(cfg.speed, 2.0)
        self.assertTrue((self.new_dir / "config.json").exists())
        self.assertEqual((self.new_dir / "data" / "cookies.pkl").read_bytes(), b"cookie-bytes")
        # cookies path saved by the old version is redirected to the new data dir
        self.assertEqual(cfg.cookies_path, str(self.new_dir / "data" / "cookies.pkl"))
        # old files are left in place
        self.assertTrue(self.old_config.exists())
        self.assertTrue(self.old_cookies.exists())

    def test_new_config_wins_over_legacy(self):
        self.old_config.write_text(json.dumps({"api_key": "sk-old"}), encoding="utf-8")
        (self.new_dir).mkdir(parents=True)
        (self.new_dir / "config.json").write_text(json.dumps({"api_key": "sk-new"}), encoding="utf-8")

        self.assertEqual(XXTConfig.load().api_key, "sk-new")

    def test_explicit_path_never_triggers_migration(self):
        self.old_config.write_text(json.dumps({"api_key": "sk-old"}), encoding="utf-8")
        missing = Path(self._tmp.name) / "elsewhere.json"

        cfg = XXTConfig.load(missing)

        self.assertEqual(cfg.api_key, "")
        self.assertFalse((self.new_dir / "config.json").exists())

    @unittest.skipIf(os.name == "nt", "POSIX permissions only")
    def test_saved_config_is_owner_only(self):
        target = self.new_dir / "config.json"
        XXTConfig(api_key="sk-x").save(target)
        mode = stat.S_IMODE(target.stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_missing_font_dict_path_falls_back_to_bundled(self):
        target = self.new_dir / "config.json"
        XXTConfig(font_dict_path="/no/such/font_dict.txt").save(target)
        cfg = XXTConfig.load(target)
        self.assertEqual(cfg.font_dict_path, str(cfgmod.RESOURCE_DIR / "font_dict.txt"))


class TestPackageExports(unittest.TestCase):
    def test_public_names_resolve(self):
        import xxt_agent

        for name in xxt_agent.__all__:
            self.assertTrue(hasattr(xxt_agent, name), name)

    def test_old_core_package_is_gone(self):
        with self.assertRaises(ImportError):
            import xxt_agent.core  # noqa: F401

    def test_tool_schema_available(self):
        from xxt_agent.tool_schema import get_agent_tools_schema

        self.assertTrue(get_agent_tools_schema())


if __name__ == "__main__":
    unittest.main()
