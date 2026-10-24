import json
import pathlib
import re
import unittest

from gag_mcp import core

ROOT = pathlib.Path(__file__).parents[1]
SCRIPT = (ROOT / "scripts" / "fetch_upstreams.sh").read_text()
LOCK = ROOT / "src" / "gag_mcp" / "_upstream" / "UPSTREAM_LOCK.json"


def _pin(name: str) -> str:
    return re.search(rf'^DEFAULT_{name}_REF="([0-9a-f]{{40}})"', SCRIPT, re.M).group(1)


class BundleTests(unittest.TestCase):
    def test_bundle_lock_matches_fetch_pins(self):
        lock = json.loads(LOCK.read_text())["upstreams"]
        self.assertEqual(lock["toolkit"]["commit"], _pin("TOOLKIT"))
        self.assertEqual(lock["agentic"]["commit"], _pin("AGENTIC"))
        for entry in lock.values():
            self.assertTrue(entry["tree_digest"].startswith("sha256:"))
            self.assertGreater(entry["file_count"], 0)

    def test_bundled_upstreams_resolve_without_env(self):
        import os
        if os.environ.get("GAG_TOOLKIT_PATH") or os.environ.get("GAG_AGENTIC_PATH"):
            self.skipTest("explicit upstream override set")
        self.assertTrue((core.toolkit_root() / "LICENSE").is_file())
        self.assertTrue((core.agentic_root() / "LICENSE").is_file())
        self.assertEqual(core._source_commit("toolkit", "GAG_TOOLKIT_PATH", core.toolkit_root()), _pin("TOOLKIT")[:7])
        self.assertEqual(core._source_commit("agentic", "GAG_AGENTIC_PATH", core.agentic_root()), _pin("AGENTIC")[:7])


if __name__ == "__main__":
    unittest.main()
