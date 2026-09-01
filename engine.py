#!/usr/bin/env python3
"""Evidence-contracts reference engine for the contribution-edge fixtures.

One job: read the fixture package's six fixture files plus TYPED-NEGATIVES.md,
parse each embedded ```yaml record strictly (unknown or missing fields fail
loudly), and emit per fixture {fixture_id, file, pass, reasons[]} — pass/fail
only. The engine validates that every effect field stays `none` and that
`implementation_status` stays `fixture_only`. It computes nothing else: no
reward, credit, payout, score, standing, or ranking arithmetic exists here,
and the output schema cannot express it (see assert_meta_negatives_inexpressible).

The fixture package is local research. Every receipt this engine writes
banners the same line:

    fixture run receipt — not economy validation

Strictness contract (the graft is fail-closed by design):
  - the record schema is CLOSED: unknown field, missing field, duplicate key,
    wrong shape (a list field given a scalar), tab, blank line, flow YAML,
    or an anchor/tag inside a value all fail with a reason;
  - the fixture set is PINNED: the engine reads exactly the six fixture files
    and TYPED-NEGATIVES.md of validation/contribution-edge-fixtures/, and any
    drift in that read set or in the seven typed negatives is fatal (exit 2);
  - receipts are DETERMINISTIC: same fixture bytes -> byte-identical
    receipt (no timestamps, no random ids), written atomically to var/.

Surfaces: importable functions (parse_record, validate_record,
run_fixtures, ...) and a standalone CLI. No network, no subprocess.
Writes only var/ receipts.

Exit codes: 0 all fixtures pass; 1 run completed with failing fixtures;
2 fatal (usage error, fixture-set drift, unreadable read set).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile

ENGINE_VERSION = "0.1.0"
RECEIPT_SCHEMA = "evidence-fixtures-run/1"
RECEIPT_BANNER = "fixture run receipt — not economy validation"

# The pinned read set: exactly these seven files of the fixture package.
FIXTURE_FILES = (
    "fixture-positive-observed-use.md",
    "fixture-invisible-work-exclusion.md",
    "fixture-authority-handoff-no-effect.md",
    "fixture-appeal-recusal.md",
    "fixture-attention-capture.md",
    "fixture-reviewer-bottleneck.md",
)
TYPED_NEGATIVES_FILE = "TYPED-NEGATIVES.md"
READ_SET = FIXTURE_FILES + (TYPED_NEGATIVES_FILE,)

# Closed record contract (SCHEMA.md). Order is the reason-reporting order.
RECORD_FIELDS = (
    "fixture_id",
    "local_research_status",
    "source_posture",
    "source_refs",
    "input_event",
    "observed_signal",
    "review_action",
    "expected_credit_state",
    "forbidden_state_mutations",
    "reward_effect",
    "authority_effect",
    "policy_effect",
    "governance_effect",
    "payout_effect",
    "implementation_status",
    "typed_negative",
    "deterministic_check",
    "review_check",
    "owner_route",
    "blocked_escalation",
    "open_residue",
)
SCALAR_FIELDS = tuple(f for f in RECORD_FIELDS if f not in ("source_refs", "forbidden_state_mutations"))
LIST_FIELDS = ("source_refs", "forbidden_state_mutations")
EFFECT_FIELDS = (
    "reward_effect",
    "authority_effect",
    "policy_effect",
    "governance_effect",
    "payout_effect",
)
IMPLEMENTATION_STATUS_EXPECTED = "fixture_only"
LOCAL_RESEARCH_STATUSES = ("research-pass", "research-flag", "research-block")

# The seven typed negatives of TYPED-NEGATIVES.md, pinned verbatim.
EXPECTED_TYPED_NEGATIVES = (
    "observed_signal -> reviewed_credit",
    "reviewed_credit -> reward_effect",
    "reviewed_credit -> authority_effect",
    "attention_route -> governance_effect",
    "fixture_pass -> economy_validated",
    "fixture_package -> implementation_readiness",
    "reviewer_status -> standing_authority",
)
# The two meta-negatives hold by construction: the closed output schema below
# has no field that could carry either transition.
META_TYPED_NEGATIVES = (
    "fixture_pass -> economy_validated",
    "fixture_package -> implementation_readiness",
)

# Closed output vocabulary. Per fixture: exactly these four keys, nothing else.
RESULT_KEYS = ("fixture_id", "file", "pass", "reasons")
RECEIPT_KEYS = (
    "schema",
    "banner",
    "engine_version",
    "fixture_set_hash",
    "typed_negatives_held",
    "results",
    "fixtures_passed",
    "fixtures_total",
)
# No output key may carry (or even name) what the meta-negatives reject.
FORBIDDEN_OUTPUT_TOKENS = ("economy", "readiness", "validated")

MAX_SCALAR = 2048

_KEY_LINE_RE = re.compile(r"^([a-z][a-z0-9_]*):(.*)$")
_ITEM_LINE_RE = re.compile(r"^  - (.*)$")
_MUTATION_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_FENCE_OPEN = "```yaml"
_FENCE_CLOSE = "```"


class StrictRecordError(Exception):
    """A fixture record failed strict parsing; carries fail-loud reasons."""

    def __init__(self, reasons):
        super().__init__("; ".join(reasons))
        self.reasons = list(reasons)


class FixtureSetError(Exception):
    """The pinned read set itself drifted or is unreadable (fatal, exit 2)."""


# ---------------------------------------------------------------------------
# Strict flat-key YAML record parsing (stdlib, no yaml dependency)
# ---------------------------------------------------------------------------


def _reject_scalar(value, where, reasons):
    if value == "":
        reasons.append(f"{where}: empty value")
        return
    if len(value) > MAX_SCALAR:
        reasons.append(f"{where}: value longer than {MAX_SCALAR} characters")
    for ch in value:
        if ord(ch) < 0x20 or ord(ch) == 0x7F:
            reasons.append(f"{where}: control character in value")
            return
    if value[:1] in ("{", "[", "&", "*", "!", "|", ">", "'", '"', "#"):
        reasons.append(f"{where}: value must be plain text, not YAML flow/anchor/scalar syntax")


def extract_yaml_block(text, origin="record"):
    """Extract the single ```yaml fenced block of a fixture markdown file.

    Anything outside the fences is fixture prose and may vary freely; inside
    the fences every line must obey the flat-key record grammar.
    """
    lines = text.split("\n")
    open_idx = None
    close_idx = None
    for idx, line in enumerate(lines):
        stripped = line.rstrip()
        if stripped == _FENCE_OPEN:
            if open_idx is not None:
                raise StrictRecordError([f"{origin}: more than one ```yaml block"])
            open_idx = idx
        elif stripped == _FENCE_CLOSE and open_idx is not None and close_idx is None:
            close_idx = idx
    if open_idx is None:
        raise StrictRecordError([f"{origin}: no ```yaml record block found"])
    if close_idx is None:
        raise StrictRecordError([f"{origin}: ```yaml block is never closed"])
    if close_idx == open_idx + 1:
        raise StrictRecordError([f"{origin}: ```yaml block is empty"])
    return lines[open_idx + 1 : close_idx]


def parse_flat_record(lines, origin="record"):
    """Parse the strict flat-key subset of YAML the fixtures use.

    Grammar: `key: value` scalar entries and `key:` followed by contiguous
    `  - item` block-sequence entries. Nothing else — no comments, no blank
    lines, no tabs, no flow style, no nesting, no duplicate keys. Unknown
    and missing fields fail loudly against the closed RECORD_FIELDS set.
    """
    reasons = []
    record: dict = {}
    pending_list_key = None

    def fail(message):
        reasons.append(f"{origin} line {lineno}: {message}")

    for lineno, raw in enumerate(lines, 1):
        line = raw.rstrip()
        if "\t" in raw:
            fail("tab character is not allowed in a record block")
            continue
        if line.strip() == "":
            fail("blank line inside record block")
            continue
        item = _ITEM_LINE_RE.match(line)
        if item:
            if pending_list_key is None:
                fail("sequence item without an open list field")
                continue
            value = item.group(1).strip()
            where = f"{origin} line {lineno} ({pending_list_key}[])"
            _reject_scalar(value, where, reasons)
            record[pending_list_key].append(value)
            continue
        pending_list_key = None
        entry = _KEY_LINE_RE.match(line)
        if not entry:
            fail("line is neither 'key: value' nor a '  - item' sequence entry")
            continue
        key, rest = entry.group(1), entry.group(2)
        if key in record:
            fail(f"duplicate key {key!r}")
            continue
        if key in LIST_FIELDS:
            if rest.strip() != "":
                fail(f"list field {key!r} must be a block sequence ('key:' then '  - item'), not a scalar")
                continue
            record[key] = []
            pending_list_key = key
        else:
            if rest == "":
                fail(f"scalar field {key!r} has an empty value")
                continue
            if not rest.startswith(" "):
                fail("expected exactly one space after the colon")
                continue
            value = rest[1:].strip()
            _reject_scalar(value, f"{origin} line {lineno} ({key})", reasons)
            record[key] = value

    unknown = sorted(k for k in record if k not in RECORD_FIELDS)
    for key in unknown:
        reasons.append(f"{origin}: unknown field {key!r} (record contract is closed)")
    missing = [k for k in RECORD_FIELDS if k not in record]
    for key in missing:
        reasons.append(f"{origin}: missing required field {key!r}")
    for key in LIST_FIELDS:
        if key in record and not record[key]:
            reasons.append(f"{origin}: list field {key!r} has no entries")
    if reasons:
        raise StrictRecordError(reasons)
    return record


def parse_fixture_record(text, origin="record"):
    """Parse one fixture file body into a validated-shape record (or raise)."""
    return parse_flat_record(extract_yaml_block(text, origin=origin), origin=origin)


# ---------------------------------------------------------------------------
# Per-fixture validation
# ---------------------------------------------------------------------------


def expected_fixture_id(filename):
    """fixture-positive-observed-use.md -> positive-observed-use stem."""
    stem = filename
    if stem.startswith("fixture-"):
        stem = stem[len("fixture-") :]
    if stem.endswith(".md"):
        stem = stem[: -len(".md")]
    return stem


def validate_record(record, filename):
    """Validate one parsed record. Returns a list of reasons (empty = pass)."""
    reasons = []

    want_suffix = "-" + expected_fixture_id(filename)
    if not record["fixture_id"].endswith(want_suffix):
        reasons.append(
            f"fixture_id {record['fixture_id']!r} does not match filename {filename!r} "
            f"(expected it to end with {want_suffix!r})"
        )
    if record["local_research_status"] not in LOCAL_RESEARCH_STATUSES:
        reasons.append(
            f"local_research_status must be one of {', '.join(LOCAL_RESEARCH_STATUSES)}; "
            f"got {record['local_research_status']!r}"
        )
    for field in LIST_FIELDS:
        for item in record[field]:
            if field == "forbidden_state_mutations" and not _MUTATION_NAME_RE.match(item):
                reasons.append(f"forbidden_state_mutations entries must be identifiers; got {item!r}")
    # Non-collapse defaults: the whole point. All five, always none.
    for field in EFFECT_FIELDS:
        if record[field] != "none":
            reasons.append(f"non-collapse default violated: {field} must be none; got {record[field]!r}")
    if record["implementation_status"] != IMPLEMENTATION_STATUS_EXPECTED:
        reasons.append(
            f"implementation_status must be {IMPLEMENTATION_STATUS_EXPECTED!r}; got {record['implementation_status']!r}"
        )
    if " -> " not in record["typed_negative"]:
        reasons.append("typed_negative must state a rejected transition ('A -> B ...')")
    for field in ("deterministic_check", "review_check"):
        if record[field].strip() == "":
            reasons.append(f"{field} must be present and non-empty")
    for field in ("owner_route", "blocked_escalation", "open_residue"):
        if record[field].strip() == "":
            reasons.append(f"safety field {field} must be present and non-empty (never stripped)")
    return reasons


# ---------------------------------------------------------------------------
# TYPED-NEGATIVES.md parsing
# ---------------------------------------------------------------------------


def parse_typed_negatives(text, origin=TYPED_NEGATIVES_FILE):
    """Parse the typed-negatives table strictly.

    Returns the list of negative names. Any drift from the pinned seven
    (names, verdicts, table shape) raises FixtureSetError.
    """
    reasons = []
    names = []
    lines = text.split("\n")
    if "Status: active negative-control scaffold" not in lines:
        reasons.append(f"{origin}: header line 'Status: active negative-control scaffold' is missing or changed")
    if "Promotion scope: local-research-only" not in lines:
        reasons.append(f"{origin}: header line 'Promotion scope: local-research-only' is missing or changed")
    header_idx = None
    for idx, line in enumerate(lines):
        cells = [cell.strip() for cell in line.split("|")]
        if cells[:2] == ["", "Typed negative"] and cells[1:4] == ["Typed negative", "Verdict", "Covered by"]:
            header_idx = idx
            break
    if header_idx is None:
        reasons.append(f"{origin}: table header '| Typed negative | Verdict | Covered by |' not found")
    else:
        if header_idx + 1 >= len(lines) or not lines[header_idx + 1].replace("|", "").replace("-", "").strip() == "":
            reasons.append(f"{origin}: table separator row '| --- | --- | --- |' not found under the header")
        for line in lines[header_idx + 2 :]:
            if line.strip() == "":
                break
            cells = [cell.strip() for cell in line.split("|")]
            if len(cells) < 5:
                reasons.append(f"{origin}: malformed table row (expected 3 cells): {line.strip()[:120]!r}")
                continue
            name_cell, verdict, covered = cells[1], cells[2], cells[3]
            name_match = re.match(r"^`([^`]+)`", name_cell)
            if not name_match:
                reasons.append(f"{origin}: negative cell must open with a backtick-quoted name: {name_cell[:60]!r}")
                continue
            name = name_match.group(1)
            if verdict != "rejected":
                reasons.append(f"{origin}: typed negative {name!r} must have verdict 'rejected'; got {verdict!r}")
            if covered == "":
                reasons.append(f"{origin}: typed negative {name!r} has an empty 'Covered by' cell")
            names.append(name)
        pinned = list(EXPECTED_TYPED_NEGATIVES)
        for name in names:
            if name not in pinned:
                reasons.append(f"{origin}: unexpected typed negative {name!r} (pinned set has {len(pinned)})")
        for name in pinned:
            if name not in names:
                reasons.append(f"{origin}: pinned typed negative {name!r} missing from the table")
    if reasons:
        raise FixtureSetError("; ".join(reasons))
    return names


def assert_meta_negatives_inexpressible():
    """Prove the two meta-negatives hold by construction.

    `fixture_pass -> economy_validated` and
    `fixture_package -> implementation_readiness` cannot be expressed because
    the output schema is closed: results carry only pass/fail state and no
    receipt key names (or could name) an economy-validation or
    implementation-readiness field. Returns a list of reasons (empty = holds).
    """
    reasons = []
    for key in RECEIPT_KEYS + RESULT_KEYS:
        for token in FORBIDDEN_OUTPUT_TOKENS:
            if token in key:
                reasons.append(f"output key {key!r} could express a forbidden transition (token {token!r})")
    return reasons


# ---------------------------------------------------------------------------
# Run: read -> parse -> validate -> emit
# ---------------------------------------------------------------------------


def compute_fixture_set_hash(digests):
    """Hash the FULL read set (all six fixtures AND TYPED-NEGATIVES.md).

    digests maps file name -> sha256 hex of its bytes. Order is sorted file
    name; the digest bytes are mixed in binary so the hash is unambiguous.
    """
    fixture_hash = hashlib.sha256()
    for name in sorted(digests):
        fixture_hash.update(name.encode("utf-8"))
        fixture_hash.update(b"\0")
        fixture_hash.update(bytes.fromhex(digests[name]))
    return "sha256:" + fixture_hash.hexdigest()


def _read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


def run_fixtures(fixtures_dir, var_dir=None, write_receipt=True):
    """Run the pinned fixture set. Returns the receipt dict.

    Reads exactly READ_SET from fixtures_dir; parses each fixture's record
    strictly; validates the non-collapse defaults; verifies the seven typed
    negatives; proves the two meta-negatives inexpressible; emits the
    deterministic receipt. When write_receipt is true the receipt is written
    atomically to <var_dir>/receipt.json (default: <addon>/var/receipt.json).
    Raises FixtureSetError when the pinned read set itself has drifted.
    """
    if not os.path.isdir(fixtures_dir):
        raise FixtureSetError(f"fixtures directory not found: {os.path.basename(fixtures_dir)!r}")

    digests = {}
    texts = {}
    for name in READ_SET:
        path = os.path.join(fixtures_dir, name)
        if not os.path.isfile(path):
            raise FixtureSetError(f"pinned read set drifted: expected file {name!r} is missing")
        data = _read_bytes(path)
        digests[name] = hashlib.sha256(data).hexdigest()
        try:
            texts[name] = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FixtureSetError(f"{name}: not valid UTF-8 ({exc})") from exc

    parse_typed_negatives(texts[TYPED_NEGATIVES_FILE])

    results = []
    for name in FIXTURE_FILES:
        origin = name
        try:
            record = parse_fixture_record(texts[name], origin=origin)
            reasons = validate_record(record, name)
            fixture_id = record["fixture_id"]
        except StrictRecordError as exc:
            reasons = exc.reasons
            fixture_id = ""
        results.append(
            {
                "fixture_id": fixture_id,
                "file": name,  # basename only: receipts stay home-path-free
                "pass": reasons == [],
                "reasons": reasons,
            }
        )

    meta_reasons = assert_meta_negatives_inexpressible()
    if meta_reasons:
        raise FixtureSetError("output schema could not prove the meta-negatives: " + "; ".join(meta_reasons))

    receipt = {
        "schema": RECEIPT_SCHEMA,
        "banner": RECEIPT_BANNER,
        "engine_version": ENGINE_VERSION,
        "fixture_set_hash": compute_fixture_set_hash(digests),
        "typed_negatives_held": len(EXPECTED_TYPED_NEGATIVES),
        "results": results,
        "fixtures_passed": sum(1 for result in results if result["pass"]),
        "fixtures_total": len(results),
    }
    if write_receipt:
        write_receipt_atomically(receipt, var_dir or default_var_dir())
    return receipt


def default_var_dir():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "var")


def receipt_bytes(receipt):
    """Canonical receipt serialization — the bytes that must be identical."""
    return (json.dumps(receipt, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def write_receipt_atomically(receipt, var_dir):
    """Write var/receipt.json via temp + os.replace so parallel runs and
    readers never observe a partial file."""
    os.makedirs(var_dir, exist_ok=True)
    final = os.path.join(var_dir, "receipt.json")
    handle = tempfile.NamedTemporaryFile(
        mode="wb", dir=var_dir, prefix=".receipt-tmp-", suffix=".part", delete=False
    )
    try:
        with handle:
            handle.write(receipt_bytes(receipt))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(handle.name, final)
    except BaseException:
        try:
            os.unlink(handle.name)
        except OSError:
            pass
        raise
    return final


# ---------------------------------------------------------------------------
# Standalone CLI
# ---------------------------------------------------------------------------


def main(argv):
    if len(argv) != 2 or argv[1] in ("-h", "--help"):
        sys.stderr.write("usage: python3 engine.py <fixtures-dir>\n")
        return 2
    try:
        receipt = run_fixtures(argv[1])
    except FixtureSetError as exc:
        sys.stderr.write(f"engine: fatal: {exc}\n")
        return 2
    except OSError as exc:
        sys.stderr.write(f"engine: fatal: {exc}\n")
        return 2
    sys.stdout.write(receipt_bytes(receipt).decode("utf-8"))
    failed = [result["file"] for result in receipt["results"] if not result["pass"]]
    if failed:
        sys.stderr.write(f"engine: {receipt['fixtures_passed']}/{receipt['fixtures_total']} fixtures pass; failed: {', '.join(failed)}\n")
        return 1
    sys.stderr.write(
        f"engine: {receipt['fixtures_passed']}/{receipt['fixtures_total']} fixtures pass, "
        f"{receipt['typed_negatives_held']}/{len(EXPECTED_TYPED_NEGATIVES)} typed negatives hold "
        f"(all effect fields none) — receipt: var/receipt.json\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
