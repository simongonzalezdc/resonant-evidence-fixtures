#!/usr/bin/env python3
"""A6/A10 harness for the evidence-contracts reference engine.

Run: python3 engine_test.py

Gates carried here (PRD acceptance):
  - kill test (A3): the real fixture package parses 6/6 and all 7 typed
    negatives hold with every effect field `none`;
  - adversarial (A6): malformed fixtures FAIL-with-reason, never crash;
    unknown fields fail; output keys stay closed; no home path in output;
  - determinism (A10): same fixtures -> byte-identical receipt, including
    N=4 parallel runs writing the same receipt path, zero partial files;
  - non-collapse grep gate (A4): the pinned computation-pattern list
    (reward / credit / payout / score / standing / rank class) has ZERO
    matches in engine.py and server.py, and no receipt ever carries an
    effect-field value;
  - attribution (A5): zero kinocut source fingerprints vendored;
  - write confinement (A8): a run touches nothing in the fixtures
    directory (bit-identical before/after) and writes only under var/.

The fixture directory is resolved from CONTRACTS_GIFT_FIXTURES_DIR (your
checkout of validation/contribution-edge-fixtures/). No machine-specific
path is stored in this file.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import engine  # noqa: E402

ENGINE_PY = os.path.join(HERE, "engine.py")

def resolve_fixtures_dir():
    """Fixture directory comes from the environment — the harness stores no
    machine-specific paths. Set CONTRACTS_GIFT_FIXTURES_DIR to a checkout of
    the contribution-edge-fixtures package (validation/contribution-edge-fixtures/).
    """
    env_dir = os.environ.get("CONTRACTS_GIFT_FIXTURES_DIR")
    return env_dir if env_dir else None


def require_fixtures(test):
    """Return the configured fixtures dir, or fail the test with instructions."""
    fixtures_dir = resolve_fixtures_dir()
    if not fixtures_dir or not os.path.isdir(fixtures_dir):
        test.fail(
            "fixture package not configured: set CONTRACTS_GIFT_FIXTURES_DIR "
            "to your checkout of validation/contribution-edge-fixtures/"
        )
    return fixtures_dir


def run_cli(fixtures_dir, var_dir=None):
    """Run the engine CLI in a subprocess. Returns (exit_code, stdout, stderr)."""
    env = dict(os.environ)
    args = [sys.executable, ENGINE_PY, fixtures_dir]
    if var_dir is not None:
        # CLI has a single pinned contract; run inside a temp cwd does not
        # change var (it is addon-relative), so parallel isolation is done by
        # snapshotting, not by moving var.
        pass
    proc = subprocess.run(args, capture_output=True, text=True, env=env, cwd=HERE)
    return proc.returncode, proc.stdout, proc.stderr


def copy_fixtures(fixtures_dir):
    tmp = tempfile.mkdtemp(prefix="contracts-gift-fixtures-")
    for name in engine.READ_SET:
        shutil.copy2(os.path.join(fixtures_dir, name), os.path.join(tmp, name))
    return tmp


def read_text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


class FixtureBacked(unittest.TestCase):
    """Base: every fixture-backed test resolves the dir at test time."""

    def fixtures(self):
        return require_fixtures(self)


# ---------------------------------------------------------------------------
# A4: pinned non-collapse computation-pattern list (pinned at implementation
# time, per PRD A10 note). Zero matches allowed in engine.py and server.py.
# ---------------------------------------------------------------------------

A4_GREP_PATTERNS = [
    # augmented assignment over the guarded vocabulary
    re.compile(r"(?i)\b(reward|credit|payout|score|standing|rank)\w*\s*(\+|-|\*|/|%|>>|<<)="),
    # arithmetic over a guarded token and a numeric literal
    re.compile(r"(?i)\b(reward|credit|payout|score|standing|rank)\w*\s*[-+*/]\s*\d"),
    # numeric literal folded into a guarded token
    re.compile(r"(?i)\d\s*[-+*/]\s*\w*(reward|payout|score|standing|rank)"),
    # guarded token coerced to a number (computation prep)
    re.compile(r"(?i)\b(?:int|float|round|abs|sum|max|min)\s*\([^)]*\b(reward|payout|score|standing|rank)"),
    # any sum reduction over the guarded vocabulary (counting fixtures is fine)
    re.compile(r"(?i)\bsum\s*\([^)]*\b(reward|credit|payout|score|standing|rank)"),
]

# A5: kinocut source fingerprints. None of these identifiers may appear
# anywhere in the gift tree — pattern-level adaptation, zero vendored bytes.
A5_KINOCUT_FINGERPRINTS = [
    "RecordBase",
    "canonical_record_id",
    "MCPVideoError",
    "ValueObject",
    "ConfigDict",
    "pydantic",
    "model_config",
    "record_kind",
    "supersedes",
    "NormalizedRegion",
    "AiVideoReceiptSection",
    "kinocut.contracts",
    "allow_inf_nan",
]


def addon_source_files():
    """Every repo text file of the gift (engine, server, tests, docs, manifests)."""
    skip_dirs = {"__pycache__", "var", ".git"}
    found = []
    for root, dirs, files in os.walk(HERE):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for name in files:
            if name.endswith((".py", ".md", ".json", ".sh", ".cfg", ".toml")):
                found.append(os.path.join(root, name))
    return sorted(found)


class KillTest(FixtureBacked):
    """A3: the real package passes 6/6 with 7/7 typed negatives, effects none."""


    def test_kill_test_all_pass(self):
        with tempfile.TemporaryDirectory() as var_dir:
            receipt = engine.run_fixtures(self.fixtures(), var_dir=var_dir)
        self.assertEqual(receipt["fixtures_total"], 6)
        self.assertEqual(receipt["fixtures_passed"], 6, json.dumps(receipt["results"], indent=2))
        self.assertEqual(receipt["typed_negatives_held"], 7)
        self.assertEqual(receipt["schema"], engine.RECEIPT_SCHEMA)
        self.assertEqual(receipt["banner"], "fixture run receipt — not economy validation")
        for result in receipt["results"]:
            self.assertEqual(sorted(result.keys()), sorted(engine.RESULT_KEYS))
            self.assertTrue(result["pass"], f"{result['file']}: {result['reasons']}")
            self.assertEqual(result["reasons"], [])

    def test_cli_exit_zero_and_receipt(self):
        code, out, err = run_cli(self.fixtures())
        self.assertEqual(code, 0, err)
        receipt = json.loads(out)
        self.assertEqual(receipt["fixtures_passed"], 6)
        self.assertTrue(os.path.isfile(os.path.join(HERE, "var", "receipt.json")))

    def test_meta_negatives_hold_by_construction(self):
        self.assertEqual(engine.assert_meta_negatives_inexpressible(), [])
        # tamper: an output vocabulary that could carry the transition is caught
        original = engine.RECEIPT_KEYS
        engine.RECEIPT_KEYS = original + ("economy_validated",)
        try:
            reasons = engine.assert_meta_negatives_inexpressible()
        finally:
            engine.RECEIPT_KEYS = original
        self.assertTrue(any("economy_validated" in reason for reason in reasons))


class Adversarial(FixtureBacked):
    """A6: malformed fixtures fail-with-reason, never crash; privacy holds."""


    def setUp(self):
        self.dir = copy_fixtures(self.fixtures())
        self.addCleanup(shutil.rmtree, self.dir, True)

    def mutate(self, name, old, new, count=1):
        path = os.path.join(self.dir, name)
        text = read_text(path)
        self.assertIn(old, text, f"mutation target not found in {name}")
        path_new = text.replace(old, new, count)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(path_new)

    def run_engine(self):
        with tempfile.TemporaryDirectory() as var_dir:
            try:
                receipt = engine.run_fixtures(self.dir, var_dir=var_dir)
                return 0, receipt, None
            except engine.FixtureSetError as exc:
                return 2, None, str(exc)

    def assert_result_fails_with_reason(self, receipt, filename, needle):
        entry = next(r for r in receipt["results"] if r["file"] == filename)
        self.assertFalse(entry["pass"])
        self.assertTrue(entry["reasons"], f"{filename}: no reasons given")
        self.assertIn(needle, " ".join(entry["reasons"]).lower())
        others = [r for r in receipt["results"] if r["file"] != filename]
        self.assertTrue(all(r["pass"] for r in others), "collateral damage to other fixtures")

    def test_unknown_field_fails_with_reason(self):
        self.mutate(engine.FIXTURE_FILES[0], "typed_negative:", "sneaky_grant: reward\nreward_effect: none\ntyped_negative:", count=1)
        code, receipt, err = self.run_engine()
        self.assertEqual(code, 0, err)
        self.assert_result_fails_with_reason(receipt, engine.FIXTURE_FILES[0], "unknown field")

    def test_missing_field_fails_with_reason(self):
        self.mutate(engine.FIXTURE_FILES[1], "open_residue:", "open_residuex:", count=1)
        code, receipt, err = self.run_engine()
        self.assertEqual(code, 0, err)
        self.assert_result_fails_with_reason(receipt, engine.FIXTURE_FILES[1], "missing required field")

    def test_effect_field_not_none_fails(self):
        self.mutate(engine.FIXTURE_FILES[2], "reward_effect: none", "reward_effect: bounded_credit", count=1)
        code, receipt, err = self.run_engine()
        self.assertEqual(code, 0, err)
        self.assert_result_fails_with_reason(receipt, engine.FIXTURE_FILES[2], "reward_effect")

    def test_implementation_status_not_fixture_only_fails(self):
        self.mutate(engine.FIXTURE_FILES[3], "implementation_status: fixture_only", "implementation_status: shipped", count=1)
        code, receipt, err = self.run_engine()
        self.assertEqual(code, 0, err)
        self.assert_result_fails_with_reason(receipt, engine.FIXTURE_FILES[3], "implementation_status")

    def test_unclosed_yaml_block_fails(self):
        path = os.path.join(self.dir, engine.FIXTURE_FILES[4])
        text = read_text(path)
        text = text.replace("```", "", 1)  # drop the OPENING fence line marker
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        code, receipt, err = self.run_engine()
        self.assertEqual(code, 0, err)
        self.assert_result_fails_with_reason(receipt, engine.FIXTURE_FILES[4], "record block")

    def test_list_field_given_scalar_fails(self):
        self.mutate(engine.FIXTURE_FILES[0], "source_refs:\n", "source_refs: scalar-ref\n", count=1)
        code, receipt, err = self.run_engine()
        self.assertEqual(code, 0, err)
        self.assert_result_fails_with_reason(receipt, engine.FIXTURE_FILES[0], "block sequence")

    def test_duplicate_key_fails(self):
        self.mutate(engine.FIXTURE_FILES[5], "payout_effect: none", "payout_effect: none\ngovernance_effect: none", count=1)
        code, receipt, err = self.run_engine()
        self.assertEqual(code, 0, err)
        self.assert_result_fails_with_reason(receipt, engine.FIXTURE_FILES[5], "duplicate key")

    def test_blank_line_in_record_fails(self):
        self.mutate(engine.FIXTURE_FILES[0], "review_action:", "\nreview_action:", count=1)
        code, receipt, err = self.run_engine()
        self.assertEqual(code, 0, err)
        self.assert_result_fails_with_reason(receipt, engine.FIXTURE_FILES[0], "blank line")

    def test_missing_pinned_file_is_fatal_not_crash(self):
        os.remove(os.path.join(self.dir, engine.TYPED_NEGATIVES_FILE))
        code, receipt, err = self.run_engine()
        self.assertEqual(code, 2)
        self.assertIn("missing", err.lower())

    def test_typed_negatives_drift_is_fatal(self):
        path = os.path.join(self.dir, engine.TYPED_NEGATIVES_FILE)
        lines = read_text(path).split("\n")
        last_row = max(idx for idx, line in enumerate(lines) if line.startswith("| `reviewer_status"))
        lines.insert(last_row + 1, "| `new -> transition` | rejected | [MATRIX.md](MATRIX.md) |")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
        code, receipt, err = self.run_engine()
        self.assertEqual(code, 2)
        self.assertIn("unexpected typed negative", err)

    def test_cli_never_tracebacks_on_garbage_dir(self):
        proc = subprocess.run(
            [sys.executable, ENGINE_PY, os.path.join(self.dir, "not-a-real-subdir")],
            capture_output=True, text=True, cwd=HERE,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("Traceback", proc.stderr)

    def test_receipt_carries_no_absolute_paths_or_home(self):
        with tempfile.TemporaryDirectory() as var_dir:
            receipt = engine.run_fixtures(self.fixtures(), var_dir=var_dir)
            receipt_path = os.path.join(var_dir, "receipt.json")
            raw = read_bytes(receipt_path)
        home = os.path.expanduser("~")
        self.assertNotIn(home.encode(), raw)
        self.assertNotIn(b"/Users/", raw)
        for result in receipt["results"]:
            self.assertEqual(result["file"], os.path.basename(result["file"]))

    def test_result_keys_stay_closed(self):
        with tempfile.TemporaryDirectory() as var_dir:
            receipt = engine.run_fixtures(self.fixtures(), var_dir=var_dir)
        self.assertEqual(sorted(receipt.keys()), sorted(engine.RECEIPT_KEYS))
        for result in receipt["results"]:
            self.assertEqual(sorted(result.keys()), sorted(engine.RESULT_KEYS))


class Determinism(FixtureBacked):
    """A10: byte-identical receipts, sequential and 4-way parallel, no partials."""

    RECEIPT = os.path.join(HERE, "var", "receipt.json")

    def test_sequential_runs_byte_identical(self):
        with tempfile.TemporaryDirectory() as var_dir:
            engine.run_fixtures(self.fixtures(), var_dir=var_dir)
            first = read_bytes(os.path.join(var_dir, "receipt.json"))
            engine.run_fixtures(self.fixtures(), var_dir=var_dir)
            second = read_bytes(os.path.join(var_dir, "receipt.json"))
        self.assertEqual(first, second)

    def test_parallel_runs_byte_identical_no_partials(self):
        code, out, err = run_cli(self.fixtures())
        self.assertEqual(code, 0, err)
        reference = read_bytes(self.RECEIPT)

        snapshots = []
        lock = threading.Lock()

        def worker():
            proc = subprocess.run([sys.executable, ENGINE_PY, self.fixtures()],
                                  capture_output=True, text=True, cwd=HERE)
            with lock:
                snapshots.append((proc.returncode, read_bytes(self.RECEIPT)))

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(len(snapshots), 4)
        for code, snapshot in snapshots:
            self.assertEqual(code, 0)
            self.assertEqual(snapshot, reference)

        leftovers = [name for name in os.listdir(os.path.dirname(self.RECEIPT)) if ".part" in name or name.startswith(".receipt-tmp-")]
        self.assertEqual(leftovers, [], "partial receipt files observed")

    def test_fixture_set_hash_binds_full_read_set(self):
        digests = {}
        for name in engine.READ_SET:
            digests[name] = hashlib.sha256(
                read_bytes(os.path.join(self.fixtures(), name))
            ).hexdigest()
        with tempfile.TemporaryDirectory() as var_dir:
            receipt = engine.run_fixtures(self.fixtures(), var_dir=var_dir)
        self.assertEqual(receipt["fixture_set_hash"], engine.compute_fixture_set_hash(digests))
        # flipping one byte of ANY read-set file must change the hash
        digests[engine.FIXTURE_FILES[0]] = "0" * 64
        self.assertNotEqual(receipt["fixture_set_hash"], engine.compute_fixture_set_hash(digests))


class GrepGates(FixtureBacked):
    """A4 + A5: pinned grep gates over the gift tree."""

    def test_a4_no_computation_over_guarded_vocabulary(self):
        offenders = []
        for path in addon_source_files():
            text = read_text(path)
            for pattern in A4_GREP_PATTERNS:
                for match in pattern.finditer(text):
                    line_no = text.count("\n", 0, match.start()) + 1
                    line = text.splitlines()[line_no - 1].strip()
                    offenders.append(f"{os.path.basename(path)}:{line_no}: {line[:120]}")
        self.assertEqual(offenders, [])

    def test_a4_receipts_never_carry_effect_values(self):
        receipt_path = os.path.join(HERE, "var", "receipt.json")
        if not os.path.isfile(receipt_path):
            with tempfile.TemporaryDirectory() as var_dir:
                receipt = engine.run_fixtures(self.fixtures(), var_dir=var_dir)
            raw = engine.receipt_bytes(receipt)
        else:
            raw = read_bytes(receipt_path)
        for field in engine.EFFECT_FIELDS:
            self.assertNotIn(field.encode(), raw, f"receipt carries {field}")
        self.assertNotIn(b'"fixture_only"', raw)

    def test_a5_zero_kinocut_bytes_vendored(self):
        # Vendored-bytes scan targets CODE (.py/.sh/.json): copied kinocut
        # source would land there. Docs (.md) are the attribution surface the
        # PRD requires to NAME the upstream patterns, so their citations are
        # expected and are not vendoring.
        offenders = []
        for path in addon_source_files():
            base = os.path.basename(path)
            if base == "engine_test.py" or base.endswith(".md"):
                continue
            text = read_text(path)
            for fingerprint in A5_KINOCUT_FINGERPRINTS:
                if fingerprint in text:
                    offenders.append(f"{base}: {fingerprint}")
        self.assertEqual(offenders, [])

    def test_engine_is_stdlib_only(self):
        text = read_text(ENGINE_PY)
        imports = re.findall(r"^\s*(?:import|from)\s+([A-Za-z_][\w.]*)", text, re.MULTILINE)
        local = {"engine"}
        for module in imports:
            top = module.split(".")[0]
            if top in local or top == "__future__":
                continue
            self.assertIn(top, {"hashlib", "json", "os", "re", "sys", "tempfile"},
                          f"engine.py imports non-stdlib module {top!r}")


class WriteConfinement(FixtureBacked):
    """A8: fixtures stay bit-identical; only var/ receives bytes."""


    def test_fixtures_bit_identical_after_run(self):
        before = {}
        for name in sorted(os.listdir(self.fixtures())):
            path = os.path.join(self.fixtures(), name)
            if os.path.isfile(path):
                before[name] = read_bytes(path)
        with tempfile.TemporaryDirectory() as var_dir:
            engine.run_fixtures(self.fixtures(), var_dir=var_dir)
            self.assertEqual(sorted(os.listdir(var_dir)), ["receipt.json"])
        after = {}
        for name in sorted(os.listdir(self.fixtures())):
            path = os.path.join(self.fixtures(), name)
            if os.path.isfile(path):
                after[name] = read_bytes(path)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
