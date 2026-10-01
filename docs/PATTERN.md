# Evidence Contracts — a pattern gift for the contribution-edge fixtures

Index:

1. What this gift is (and is not)
2. The substrate: what the fixtures already do
3. The ported patterns (kinocut-attributed), grafted onto the substrate
4. What was excluded, on purpose
5. Attribution and license
6. The honest gap

This document teaches a pattern; it does not validate an economy. Every
receipt the engine writes banners the same line:

> fixture run receipt — not economy validation

## 1. What this gift is (and is not)

A portable **evidence-contracts pattern**: record-contract discipline from
kinocut (an AI-video pipeline), grafted onto the ResonantOS community's
existing contribution-edge fixtures, plus a minimal reference engine
(`engine.py`, Python 3 stdlib only) proving the graft — the community's own
typed negatives pass with every effect field held at `none`.

Provenance: addons/contracts-gift/PRD.md (v3, consensus-approved)

The gift writes nothing but fixture pass/fail state. It computes no reward,
no credit, no payout, no score, no standing, no rank. Its output schema
cannot express "economy validated" or "implementation ready" — that is a
property of the code, checked by a test, not a promise in prose.

Provenance: engine.py (`RESULT_KEYS`, `assert_meta_negatives_inexpressible`)

## 2. The substrate: what the fixtures already do

The pattern starts from the community's own work. Their fixture package
already holds the four load-bearing moves, in their vocabulary. Any adoption
of this pattern must keep these first — the ported patterns below graft onto
them and never replace them.

### 2.1 Non-collapse defaults

Every fixture record carries five effect fields pinned to `none`, plus
`implementation_status: fixture_only`. Missing fields mean the fixture is
incomplete; the defaults must not be dropped or edited into something looser.

| Field | Default |
| --- | --- |
| `reward_effect` | `none` |
| `authority_effect` | `none` |
| `policy_effect` | `none` |
| `governance_effect` | `none` |
| `payout_effect` | `none` |
| `implementation_status` | `fixture_only` |

Provenance: validation/contribution-edge-fixtures/SCHEMA.md ("Non-Collapse Defaults")

### 2.2 Typed negatives

Rejected transitions are recorded as controls, not vibes — a table of
seven, each with a verdict (`rejected`) and the fixtures that cover it. Two
of them are meta-negatives: `fixture_pass -> economy_validated` and
`fixture_package -> implementation_readiness`.

Provenance: validation/contribution-edge-fixtures/TYPED-NEGATIVES.md

### 2.3 Blocked escalation

Every fixture names what must not happen and where escalation stops
(`blocked_escalation`), so a passing fixture cannot be silently read as
permission.

Provenance: fixture-positive-observed-use.md (`blocked_escalation` field)

### 2.4 Owner route and open residue

Every fixture names the smallest route that owns any unresolved decision
(`owner_route`) and the remaining uncertainty (`open_residue`). Decisions
stay with owners; uncertainty stays visible.

Provenance: SCHEMA.md ("Field Rules": `owner_route`, `open_residue`)

## 3. The ported patterns (kinocut-attributed), grafted onto the substrate

Each pattern below is used in kinocut's record contracts and re-expressed
here against the substrate. Pattern-level adaptation — no upstream source is
vendored (a test scans the tree for kinocut source fingerprints and fails if
any appear).

### 3.1 Immutable record base

Kinocut records are immutable and fail-closed; a record is a fact, not a
workspace. Graft: each fixture's embedded ```yaml block is parsed into a
fresh read-only record per run; the engine never mutates what it read, and
the fixtures directory is bit-identical after a run.

Provenance: kinocut/kinocut/contracts/_common.py (`RecordBase`, frozen, `allow_inf_nan=False`)

### 3.2 Closed enums

Kinocut status fields are closed enums, not free text. Graft:
`local_research_status` must be `research-pass`, `research-flag`, or
`research-block` — the three values the community's schema names — and
`implementation_status` must be exactly `fixture_only`.

Provenance: kinocut/kinocut/contracts/review.py (`EditorialDecision` closed set); validation/contribution-edge-fixtures/SCHEMA.md

### 3.3 Unknown fields fail on read

Kinocut rejects unknown fields on write and read; a typo in a record name
must never become silent data loss. Graft: the engine's record contract is
closed — an unknown field, a missing field, a duplicate key, a wrong shape
(a list field given a scalar), a tab, or a flow-style value fails loudly
with a named reason, per file.

Provenance: kinocut/kinocut/contracts/_common.py (`extra="forbid"`); graft enforced in engine.py (`parse_flat_record`)

### 3.4 Hash-bound identity

Kinocut record identity is the canonical digest of semantic content; a
supplied id that does not match is rejected. Graft: every receipt carries
`fixture_set_hash` — a sha256 over the FULL read set (all six fixture files
and TYPED-NEGATIVES.md) — so any drift in what was checked is detectable
from the receipt alone.

Provenance: kinocut/docs/AI_VIDEO_CONTRACTS.md ("ID rules"); graft enforced in engine.py (`compute_fixture_set_hash`)

### 3.5 Human-only review with derived state

Kinocut review authority is always `human` and publishability is *derived*
from records, never stored as a boolean that can rot. Graft: the fixtures
keep `review_check` (human/owner-route check) separate from
`deterministic_check` (machine check); the engine computes only the
deterministic half and never records a review verdict — review stays with
the owner route.

Provenance: kinocut/kinocut/contracts/review.py (`actor: Literal["human"]`, derived `is_publishable`); graft in engine.py (`validate_record` checks both fields present, claims neither)

### 3.6 Unknown is never zero

Kinocut cost observations make an unknown amount explicit rather than
inferring zero. Graft: the community's invisible-work fixture already says
the same thing — missing observation is not proof of no contribution; the
engine enforces the shape that keeps it that way (`open_residue` and
`owner_route` must be present and non-empty; the typed negative
`absent observed_signal -> zero value proof` stays rejected).

Provenance: kinocut/kinocut/contracts/learning.py (`CostEvent`: unknown never inferred zero); validation/contribution-edge-fixtures/fixture-invisible-work-exclusion.md

### 3.7 Advisory-only reports

Kinocut next-actions are advisory: a suggestion with no execution hook. The
gift is the same shape: `run_fixtures` emits pass/fail with reasons and a
banners receipt — there is no hook that could act on a pass, and no output
field that could carry a promotion.

Provenance: kinocut/kinocut/contracts/capability.py (`NextAction`: never an autonomy grant); graft in server.py (`run_fixtures` writes only var/receipt.json)

### 3.8 Typed negatives, honored by construction

The substrate's typed negatives are already the right idea; kinocut's
fail-closed validators show how to make them load-bearing. Graft: the
engine parses the TYPED-NEGATIVES.md table strictly (seven rows, each
verdict `rejected`), and the two meta-negatives hold **by construction** —
the closed output vocabulary is checked by a test that fails if any output
key could name what they reject.

Provenance: engine_test.py (`test_meta_negatives_hold_by_construction`); kinocut/kinocut/contracts/_errors.py (fail-closed error contract)

### 3.9 Review-as-record

Kinocut stores decisions as records bound to targets, not as edits to
prose. Graft: the fixture record itself is the record of what review
requires (`review_action`) and what review must confirm (`review_check`) —
first-class fields the engine validates for presence and never strips,
summarizes, or scores.

Provenance: kinocut/kinocut/contracts/review.py (`ReviewDecision`); validation/contribution-edge-fixtures/SCHEMA.md (field rules)

## 4. What was excluded, on purpose

Kinocut's video-specific machinery does not transfer and is not claimed:

- clips and clip verdicts; normalized regions and measurements
- preservation proofs and `ai_video` receipt sections
- content-addressed asset stores and append-only supersession graphs

Provenance: kinocut/docs/AI_VIDEO_CONTRACTS.md ("Record catalog", "Private project store")

Likewise the gift does not touch the community's own open residue
(executable JSON/YAML migration of the fixtures). That residue has an owner
route; it is theirs to decide.

## 5. Attribution and license

This gift adapts, at the pattern level, the record-contract discipline of:

**Kinocut** — Kyanite Labs, Apache-2.0.
Upstream: `https://github.com/KyaniteLabs/kinocut`
(also mirrored at `https://git.kyanitelabs.tech/KyaniteLabs/kinocut`;
contracts under `kinocut/kinocut/contracts/`; design notes in
`docs/AI_VIDEO_CONTRACTS.md`).

Ported patterns: immutable record base; closed enums; unknown-fields-fail-
on-read; hash-bound identity; human-only review with derived state;
unknown-cost-never-zero; advisory-only reports; fail-closed validation
(the typed-negative graft); review-as-record.

**Pattern-level adaptation; no upstream source vendored.** The gift is
Apache-2.0. Kinocut is Apache-2.0 with no NOTICE file; since no upstream
code is redistributed, the §4 NOTICE obligations do not trigger — this
attribution block and the upstream link satisfy §4(c)/(d) hygiene.

Provenance: kinocut/LICENSE (Apache-2.0); addons/contracts-gift/LICENSE

## 6. The honest gap

- The engine pins the fixture set at seven files and the negative table at
  seven rows. If the community edits their package, the engine fails on
  purpose (drift detection, not breakage) — updating the pins is a deliberate
  act that should be reviewed like a contract change.
- The strict parser covers the flat-key record shape the fixtures actually
  use. It is not a general YAML parser and does not try to be.
- Passing proves the non-collapse defaults hold and the typed negatives are
  still expressible controls. It proves nothing about the economy itself —
  that path runs through validation requests and external owner decisions,
  not through this gift.
