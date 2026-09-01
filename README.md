# Evidence Fixtures

> fixture run receipt — not economy validation

Kinocut's record-contract patterns, grafted onto the ResonantOS economy
community's own contribution-edge fixtures — proving those fixtures pass with
every effect field held at `none`: `reward_effect`, `authority_effect`,
`policy_effect`, `governance_effect`, `payout_effect`, and
`implementation_status: fixture_only`.

This is an evidence-contracts **pattern gift**: a reference engine
(`engine.py`, Python 3 stdlib only) plus the pattern doc that teaches the
graft. It computes nothing but fixture pass/fail state. It is not a token,
not a validator of the economy, not an implementation plan.

- Pattern doc: [docs/PATTERN.md](docs/PATTERN.md)
- Engine: `python3 engine.py <fixtures-dir>`
- Tests: `python3 engine_test.py`
- License: Apache-2.0

## The fixture package belongs to the community

The six fixtures and `TYPED-NEGATIVES.md` this engine reads live in the
community's repository, `resonantos-economy-research`, under
`validation/contribution-edge-fixtures/`. They are not included here and not
modified by this engine — the directory is bit-identical after every run
(checked by a test). Point the engine at your own checkout:

```sh
python3 engine.py /path/to/resonantos-economy-research/validation/contribution-edge-fixtures
```

Tests resolve the package the same way via `CONTRACTS_GIFT_FIXTURES_DIR`.

Exit codes: `0` all fixtures pass · `1` run completed, some fixture failed ·
`2` fatal (bad directory, fixture-set drift). The receipt lands at
`var/receipt.json` (deterministic: the same fixture bytes produce a
byte-identical receipt, including under parallel runs).

## The community's own limits, in their words

This gift exists inside the community's authorization-and-limits frame.
Their README says it better than any repackaging could — quoted verbatim:

> This repository exists for that moment. It is a **research wind tunnel**, not an
> economy factory: ideas about recognition and rewards meet source evidence, hard
> examples, rehearsals with known answers, and explicit ways to fail before anyone
> treats them as policy.

Provenance: resonantos-economy-research/README.md

> The repository is organized as **towers**. A tower is a bounded, isolated body of
> evidence built around one question or one corpus. It is *local research only* — it
> collects sources, separates what a source actually says from what we infer, and
> proposes mechanisms, invariants, and risk gates without ever turning those into
> policy.

Provenance: resonantos-economy-research/README.md

```text
  -> validation request     (a concrete fixture, not a proof)
  -> external owner decision (the only path to policy, token, governance, or launch)
```

Provenance: resonantos-economy-research/README.md

> no dispatch output can promote token policy, bounty
> policy, governance rule, payout rule, launch readiness, authority transfer, or
> economy validation by itself.

Provenance: resonantos-economy-research/README.md

Every receipt this engine writes banners the same rule:
**fixture run receipt — not economy validation**.

## What a run checks

| Check | Rule |
| --- | --- |
| Parse | Each fixture's embedded record parses strictly; unknown/missing fields, duplicate keys, wrong shapes fail loudly with reasons |
| Non-collapse defaults | All five effect fields exactly `none`; `implementation_status` exactly `fixture_only` |
| Typed negatives | All 7 hold; the 2 meta-negatives (`fixture_pass -> economy_validated`, `fixture_package -> implementation_readiness`) hold by construction — the output schema cannot express them |
| Safety fields | `owner_route`, `blocked_escalation`, `open_residue`, `typed_negative`, `deterministic_check`, `review_check` present and never stripped |
| Drift | Receipt carries a sha256 over the full read set (6 fixtures + `TYPED-NEGATIVES.md`); any change to the package changes the hash |
| Output | Per fixture: `{fixture_id, file, pass, reasons[]}` — pass/fail only |

## What it never does

- No reward, credit, payout, score, standing, or rank computation anywhere
  (a pinned grep gate in `engine_test.py` enforces this over the source).
- No network, no subprocess, no dependencies (stdlib only).
- No writes outside its own `var/receipt.json`.
- No home paths in any output (redacted; receipts carry file basenames only).
- No effect field is ever computed, emitted, or mutated — read-only.

## Running it

Standalone (no ResonantOS shell needed):

```sh
CONTRACTS_GIFT_FIXTURES_DIR=/path/to/resonantos-economy-research/validation/contribution-edge-fixtures \
python3 engine_test.py            # full gate harness (A3/A4/A5/A6/A8/A10)
sh run-validator-check.sh <path-to-2.0.0-alpha-clone>   # manifest validator gate
```

As a ResonantOS add-on (loopback local service on 127.0.0.1:4896, in-process
engine import — the service never spawns the engine):

- `contractsgift.status` — health: ok flag, addon id, engine version
- `contractsgift.run_fixtures` — `{fixtures_dir}` absolute path; same
  pass/fail receipt, persisted home-path-redacted under `var/receipt.json`

The manifest requests the `filesystem` capability only (reading the fixture
package outside the add-on tree); every tool declares it too. Grant review
is part of the design: honest friction beats a mis-declaration.

## Privacy

Local-only by construction: the engine reads your fixture checkout and
writes one receipt file. Receipts carry fixture file basenames, never
absolute paths; service responses are home-path redacted. Nothing leaves
your machine; the service binds to loopback only.

## The honest gap

The engine pins the fixture set and the typed-negative table; community
edits to their package fail loudly on purpose (update the pins deliberately).
The strict parser covers the flat-key record shape the fixtures use — it is
not a general YAML parser. A passing run proves the defaults hold and the
controls are intact; it is not economy validation. See
[docs/PATTERN.md](docs/PATTERN.md) for the full pattern, attribution, and
exclusions.
