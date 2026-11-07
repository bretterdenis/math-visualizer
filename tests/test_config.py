"""API key storage (config.json) and .env handling. Uses a temp XDG_CONFIG_HOME, never the real one."""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.backend import config


class ConfigTestCase(unittest.TestCase):
    def setUp(self):
        self._dir = Path(tempfile.mkdtemp(prefix="mathviz-cfg-"))
        self._env = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self._dir)}, clear=False)
        self._env.start()
        os.environ.pop("ANTHROPIC_API_KEY", None)
        self._platform = mock.patch.object(sys, "platform", "linux")
        self._platform.start()

    def tearDown(self):
        self._platform.stop()
        self._env.stop()
        shutil.rmtree(self._dir, ignore_errors=True)


class ApiKeyTests(ConfigTestCase):
    def test_config_path_is_under_app_folder(self):
        self.assertEqual(config.config_file(), self._dir / "math-visualizer" / "config.json")

    def test_save_then_load_uses_rust_compatible_format(self):
        config.save_api_key("sk-ant-test")
        data = json.loads((self._dir / "math-visualizer" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(data, {"api_key": "sk-ant-test"})
        self.assertEqual(config.load_api_key(), "sk-ant-test")

    def test_loads_file_written_by_rust_version(self):
        folder = self._dir / "math-visualizer"
        folder.mkdir()
        (folder / "config.json").write_text('{\n  "api_key": "sk-ant-from-rust"\n}', encoding="utf-8")
        self.assertEqual(config.load_api_key(), "sk-ant-from-rust")

    def test_env_var_takes_precedence_over_file(self):
        config.save_api_key("sk-ant-file")
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-env"
        self.assertEqual(config.load_api_key(), "sk-ant-env")

    def test_blank_env_var_is_ignored(self):
        config.save_api_key("sk-ant-file")
        os.environ["ANTHROPIC_API_KEY"] = "   "
        self.assertEqual(config.load_api_key(), "sk-ant-file")

    def test_missing_or_corrupt_file_gives_none(self):
        self.assertIsNone(config.load_api_key())
        folder = self._dir / "math-visualizer"
        folder.mkdir()
        (folder / "config.json").write_text("{broken", encoding="utf-8")
        self.assertIsNone(config.load_api_key())


class DotenvTests(ConfigTestCase):
    def test_parse_handles_quotes_export_comments_and_blank_lines(self):
        text = "# comment\n\nexport A=1\nB=\"two words\"\nC='x'\nD=val # trailing\nnoequals\n"
        self.assertEqual(
            config.parse_dotenv(text),
            {"A": "1", "B": "two words", "C": "x", "D": "val"},
        )

    def test_load_does_not_override_existing_env(self):
        env_file = self._dir / ".env"
        env_file.write_text("ANTHROPIC_API_KEY=from-dotenv\nOTHER_THING=yes\n", encoding="utf-8")
        os.environ["ANTHROPIC_API_KEY"] = "already-set"
        config.load_dotenv(env_file)
        self.assertEqual(os.environ["ANTHROPIC_API_KEY"], "already-set")
        self.assertEqual(os.environ["OTHER_THING"], "yes")
        os.environ.pop("OTHER_THING", None)

    def test_load_missing_dotenv_is_silent(self):
        config.load_dotenv(self._dir / "nope.env")


if __name__ == "__main__":
    unittest.main()
