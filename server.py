#!/usr/bin/env python3
"""addon.evidence-fixtures local-service entry (http-json on 127.0.0.1:4896).

ResonantOS add-on contract: protocol http-json, healthCommand contractsgift.status.
Wraps the evidence-contracts reference engine IN-PROCESS (a plain `import
engine`; the engine is never spawned as a subprocess, and the service itself
spawns nothing). Two verbs:

  contractsgift.status                 - ok / addon id / engine version / last run
  contractsgift.run_fixtures           - run the pinned fixture package from a
                                         fixtures directory; {fixtures_dir} required

The engine reads the fixture package read-only and writes only this add-on's
var/receipt.json. Every receipt banners: "fixture run receipt — not economy
validation". Nothing here computes reward, credit, payout, score, standing,
or rank, and no output can express economy validation or implementation
readiness (the engine's closed output schema proves this by construction).

Hardening (sibling service pattern): strict param validation with control
characters rejected (400), body capped at 64 KiB (413 + close), request
handler timeout 30 s with 408 + close on incomplete bodies, unknown fields
and unknown tools rejected, all outbound payloads and persisted receipts
home-path redacted.

Exit codes: 0 normal stop; 78 port bind failure.
"""

import json
import os
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine  # noqa: E402  (in-process import — never spawned)

PORT = int(os.environ.get("CONTRACTSGIFT_PORT", "4896"))  # dev override; manifest port 4896 is the contract
MAX_BODY = 64 * 1024
MAX_STR = 2048
ADDON_ID = "addon.evidence-fixtures"

ADDON_ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_BASE = os.path.join(ADDON_ROOT, "var")

_state = {"last_run": None}
_lock = threading.Lock()


def _check_string(name, value):
    if not isinstance(value, str) or not (0 < len(value) <= MAX_STR):
        return f"{name} must be a non-empty string of at most {MAX_STR} characters"
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in value):
        return f"{name} contains control characters"
    return None


def _validate_params(method, params):
    """Service-boundary validation. Returns an engine-argument dict or an error string."""
    if not isinstance(params, dict):
        return None, "params must be an object"
    for key in params:
        if key not in ("fixtures_dir",):
            return None, f"unknown field: {key}"

    if method == "contractsgift.status":
        if params:
            return None, "status takes no params"
        return {}, None

    if method == "contractsgift.run_fixtures":
        fixtures_dir = params.get("fixtures_dir")
        err = _check_string("fixtures_dir", fixtures_dir)
        if err:
            return None, err
        if not os.path.isabs(fixtures_dir):
            return None, "fixtures_dir must be an absolute path to the contribution-edge-fixtures directory"
        return {"fixtures_dir": fixtures_dir}, None

    return None, f"unknown method: {method}"


def _redact_text(text):
    home = os.path.expanduser("~")
    return text.replace(home, "~") if home and home != "~" else text


def _redact_obj(obj):
    if isinstance(obj, str):
        return _redact_text(obj)
    if isinstance(obj, list):
        return [_redact_obj(item) for item in obj]
    if isinstance(obj, dict):
        return {key: _redact_obj(value) for key, value in obj.items()}
    return obj


def _run_fixtures(args):
    """Execute one fixture run in-process. Returns (payload, status_code)."""
    try:
        receipt = engine.run_fixtures(args["fixtures_dir"], var_dir=OUT_BASE)
    except engine.FixtureSetError as exc:
        # fixture-set drift / bad directory: the caller's problem (400), never a crash
        return _redact_obj({"error": str(exc)}), 400
    except Exception as exc:  # honest failure, never a server crash
        return _redact_obj({"error": "fixture run failed: " + str(exc)[:300]}), 500
    failed = [result["file"] for result in receipt["results"] if not result["pass"]]
    payload = {
        "tool": "contractsgift",
        "schema": receipt["schema"],
        "banner": receipt["banner"],
        "engine_version": receipt["engine_version"],
        "fixture_set_hash": receipt["fixture_set_hash"],
        "fixtures_passed": receipt["fixtures_passed"],
        "fixtures_total": receipt["fixtures_total"],
        "typed_negatives_held": receipt["typed_negatives_held"],
        "all_pass": not failed,
        "results": receipt["results"],
        "receipt_path": "var/receipt.json",
    }
    with _lock:
        _state["last_run"] = {
            "all_pass": payload["all_pass"],
            "fixture_set_hash": payload["fixture_set_hash"],
        }
    return _redact_obj(payload), 200


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = 30  # a lying Content-Length must not pin a thread forever

    def _reply(self, code, payload, close=False):
        if close:
            self.close_connection = True  # never leave undrained bodies on a keep-alive connection
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/health"):
            self._reply(200, self._status())
        else:
            self._reply(404, {"error": "not found"}, close=True)

    def do_POST(self):
        if self.path != "/":
            self._reply(404, {"error": "not found"}, close=True)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._reply(400, {"error": "bad content-length"}, close=True)
            return
        if length <= 0 or length > MAX_BODY:
            self._reply(413 if length > MAX_BODY else 400, {"error": "body must be 1..65536 bytes"}, close=True)
            return
        try:
            req = json.loads(self.rfile.read(length).decode("utf-8"))
        except (TimeoutError, socket.timeout, OSError):
            self._reply(408, {"error": "request body incomplete (timeout)"}, close=True)
            return
        except (ValueError, UnicodeDecodeError):
            self._reply(400, {"error": "body must be valid JSON"}, close=True)
            return
        if not isinstance(req, dict):
            self._reply(400, {"error": "body must be a JSON object"}, close=True)
            return
        method = req.get("method")
        params = req.get("params", {})
        for key in req:
            if key not in ("method", "params"):
                self._reply(400, {"error": f"unknown field: {key}"}, close=True)
                return
        if not isinstance(method, str):
            self._reply(400, {"error": "method must be a string"}, close=True)
            return
        if method == "contractsgift.status":
            self._reply(200, self._status())
        elif method == "contractsgift.run_fixtures":
            args, err = _validate_params(method, params)
            if err:
                self._reply(400, {"error": err})
                return
            payload, code = _run_fixtures(args)
            self._reply(code, payload)
        else:
            self._reply(400, {"error": f"unknown tool: {method}"}, close=True)

    def _status(self):
        with _lock:
            return _redact_obj({
                "ok": True,
                "addon": ADDON_ID,
                "tool": "contractsgift",
                "engine_version": engine.ENGINE_VERSION,
                "receipt_schema": engine.RECEIPT_SCHEMA,
                "banner": engine.RECEIPT_BANNER,
                "last_run": _state["last_run"],
                "receipt_path": "var/receipt.json",
            })

    def log_message(self, fmt, *args):  # keep service logs quiet and content-free
        sys.stderr.write("evidence-fixtures-service: " + (fmt % args) + "\n")


def main():
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError as exc:
        sys.stderr.write(f"evidence-fixtures-service: cannot bind 127.0.0.1:{PORT} ({exc}); manifest entrypoint expects this port\n")
        return 78
    sys.stderr.write(f"evidence-fixtures-service: listening on http://127.0.0.1:{PORT}\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
