import pathlib
import unittest

SCRIPT = (pathlib.Path(__file__).parents[1] / "scripts" / "fetch_upstreams.sh").read_text()
EXPECTED_TOOLKIT = "afcd06d027f2bfd168233c993405060e4f18dfa1"
EXPECTED_AGENTIC = "58bdfb291df0de7c9437b4476e370a609c4b1d5f"

class SourceLockTests(unittest.TestCase):
    def test_default_refs_are_exact_full_shas(self):
        self.assertIn(f'DEFAULT_TOOLKIT_REF="{EXPECTED_TOOLKIT}"', SCRIPT)
        self.assertIn(f'DEFAULT_AGENTIC_REF="{EXPECTED_AGENTIC}"', SCRIPT)
        for value in (EXPECTED_TOOLKIT, EXPECTED_AGENTIC):
            self.assertEqual(len(value), 40)
            self.assertTrue(all(c in "0123456789abcdef" for c in value))

    def test_default_resolution_fails_closed_on_mismatch(self):
        self.assertIn('if [[ -n "$expected" && "$resolved" != "$expected" ]]', SCRIPT)
        self.assertIn("SOURCE LOCK MISMATCH", SCRIPT)

    def test_explicit_overrides_are_disclosed_as_bypassing_default_lock(self):
        self.assertIn("default exact source lock is bypassed for this fetch", SCRIPT)

if __name__ == "__main__":
    unittest.main()
