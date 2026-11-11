#!/usr/bin/env python3
"""Loopback-only, Basic-authenticated weekly cabin editor for the Raspberry Pi.

Expose only over an authenticated HTTPS tunnel / SSH port forwarding. Never publish
this admin service directly to the internet or under GitHub Pages.
"""
import base64
import fcntl
import hmac
import json
import os
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from cabins_overrides import (
    CABIN_FIELDS, GAME_FIELDS, clean_game, current_period, effective_plan, file_revision,
    game_key, load_store, make_record, override_path, save_store,
)

SOURCE = Path(os.environ.get("TUSBERNE_CABINS_SOURCE", "/home/kuhfi/infoboard-app/public/kabinen-live/kabinenplan_data.json"))
PORT = int(os.environ.get("TUSBERNE_CABINS_ADMIN_PORT", "8765"))
ORIGIN = os.environ.get("TUSBERNE_CABINS_ADMIN_ORIGIN", f"http://127.0.0.1:{PORT}").rstrip("/")
USER = os.environ.get("TUSBERNE_CABINS_ADMIN_USER", "kabinen")
HTML = Path(__file__).with_name("kabinen_admin.html")
PASSWORD_FILE = os.environ.get("TUSBERNE_CABINS_ADMIN_PASSWORD_FILE", "")


def read_raw():
    doc = json.loads(SOURCE.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or not isinstance(doc.get("games"), list) or not isinstance(doc.get("period", {}).get("weeks"), list):
        raise ValueError("Die automatische Kabinenplanung ist nicht lesbar")
    return doc


def response_state():
    raw = read_raw()
    store = load_store()
    period = current_period(raw)
    if not period:
        return {"editable": False, "reason": "Die laufende Woche fehlt in den Quelldaten", "weeks": raw.get("period", {}).get("weeks", []), "revision": file_revision()}
    start, end = period["start"], period["end"]
    original = [clean_game({k: g.get(k, False if k == "festival" else "") for k in GAME_FIELDS}, start, end)
                for g in raw["games"] if start <= g.get("date", "") <= end]
    plan = effective_plan({"period": {"weeks": [period]}, "games": original}, store)
    effective = [g for g in plan["games"] if start <= g["date"] <= end]
    return {"editable": True, "start": start, "end": end, "auto_games": original,
            "effective_games": effective, "mode": plan["manual_weeks"][start]["mode"],
            "unmatched": plan["manual_weeks"][start]["unmatched"],
            "revision": file_revision(), "updated_at": store.get("weeks", {}).get(start, {}).get("updated_at"),
            "game_keys": [game_key(g) for g in original]}


class Handler(BaseHTTPRequestHandler):
    server_version = "KabinenAdmin/1.0"

    def _headers(self, status=200, content_type="application/json; charset=utf-8", nonce=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        csp = "default-src 'none'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'; style-src 'unsafe-inline'; script-src 'nonce-" + nonce + "'" if nonce else "default-src 'none'"
        self.send_header("Content-Security-Policy", csp)

    def _json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._headers(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self):
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        try:
            raw = base64.b64decode(header[6:], validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return False
        return hmac.compare_digest(raw, self.server.auth_value)

    def _auth_or_reject(self):
        if self._authorized():
            return True
        body = b"Authorization required\n"
        self._headers(401, "text/plain; charset=utf-8")
        self.send_header("WWW-Authenticate", 'Basic realm="tus BERNE Kabinenverwaltung", charset="UTF-8"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return False

    def do_GET(self):
        if not self._auth_or_reject():
            return
        path = urlsplit(self.path).path
        if path == "/api/state":
            try:
                self._json(200, response_state())
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                self._json(503, {"error": str(exc)})
        elif path in ("/", "/index.html"):
            try:
                nonce = secrets.token_urlsafe(24)
                body = HTML.read_text(encoding="utf-8").replace("__CSP_NONCE__", nonce).encode("utf-8")
                self._headers(200, "text/html; charset=utf-8", nonce)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except OSError:
                self._json(503, {"error": "Editor-Datei fehlt"})
        else:
            self._json(404, {"error": "Nicht gefunden"})

    def do_POST(self):
        if not self._auth_or_reject():
            return
        if urlsplit(self.path).path != "/api/week":
            self._json(404, {"error": "Nicht gefunden"})
            return
        if (self.headers.get("Origin") != ORIGIN or self.headers.get("X-TUSBERNE-EDITOR") != "1"
                or not self.headers.get("Content-Type", "").lower().startswith("application/json")):
            self._json(403, {"error": "Ungültiger Ursprung der Änderung"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 220_000:
                raise ValueError("Ungültige Größe")
            request = json.loads(self.rfile.read(size).decode("utf-8"))
            if not isinstance(request, dict) or not isinstance(request.get("revision"), str):
                raise ValueError("Ungültige Eingabedaten")
            lockfile = override_path().with_suffix(".lock")
            lockfile.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with lockfile.open("a+") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                if request["revision"] != file_revision():
                    self._json(409, {"error": "Zwischenzeitlich geändert. Bitte neu laden."})
                    return
                raw = read_raw()
                start, record = make_record(raw, request.get("mode"), request)
                store = load_store()
                if record is None:
                    store["weeks"].pop(start, None)
                else:
                    store["weeks"][start] = record
                # Retain historical records only for brief local audit, not for application.
                if len(store["weeks"]) > 16:
                    for old_start in sorted(store["weeks"])[:-16]:
                        store["weeks"].pop(old_start)
                save_store(store)
            self._json(200, {"saved": True, "revision": file_revision(), "mode": request["mode"]})
        except (OSError, ValueError, KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc)})

    def log_message(self, fmt, *args):
        # No request bodies, credentials or authorization headers in logs.
        super().log_message(fmt, *args)


def main():
    if not PASSWORD_FILE:
        raise SystemExit("STOPP: TUSBERNE_CABINS_ADMIN_PASSWORD_FILE fehlt")
    password = Path(PASSWORD_FILE).read_text(encoding="utf-8").rstrip("\r\n")
    if len(password) < 16:
        raise SystemExit("STOPP: Kennwort benötigt mindestens 16 Zeichen")
    if not HTML.is_file():
        raise SystemExit("STOPP: HTML-Verwaltungsoberfläche fehlt")
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    server.auth_value = USER + ":" + password
    print(f"Kabinenverwaltung nur auf 127.0.0.1:{PORT} (Ursprung: {ORIGIN})", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()