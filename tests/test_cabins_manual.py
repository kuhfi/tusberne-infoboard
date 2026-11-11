"""Offline regression suite for the per-week cabin manual editor."""
import base64
import copy
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import socket
import sys
import tempfile
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from cabins_overrides import (clean_game, effective_plan, file_revision, game_key,
                             load_store, make_record, save_store)

NOW = datetime(2026, 11, 11, 10, 0, tzinfo=ZoneInfo("Europe/Berlin"))
G1 = dict(date="2026-11-14", time="09:30", kind="Meisterschaft", league="Bezirksliga", home="tus BERNE 1.C", away="GW Eimsbüttel", home_cabin="1", guest_cabin="3", sr_cabin="SR1", festival=False)
G2 = dict(date="2026-11-14", time="11:00", kind="Meisterschaft", league="Kreisklasse", home="tus BERNE 4.C", away="Nordlichter", home_cabin="2", guest_cabin="4", sr_cabin="SR2", festival=False)
G3 = dict(date="2026-11-21", time="10:00", kind="Meisterschaft", league="Liga", home="tus BERNE 2.B", away="Sasel", home_cabin="1", guest_cabin="3", sr_cabin="SR1", festival=False)


def source():
    return {"schema_version": 1, "generated_at": "2026-11-11T09:00:00+01:00", "period": {"weeks": [{"start": "2026-11-09", "end": "2026-11-15"}, {"start": "2026-11-16", "end": "2026-11-22"}]}, "games": [copy.deepcopy(G1), copy.deepcopy(G2), copy.deepcopy(G3)]}


class OverrideEngineTests(unittest.TestCase):
    def test_default_is_automatic_and_no_mutation(self):
        raw = source()
        original = copy.deepcopy(raw)
        plan = effective_plan(raw, {"schema_version": 1, "weeks": {}}, NOW)
        self.assertEqual(plan["games"], raw["games"])
        self.assertEqual(raw, original)
        self.assertEqual(plan["manual_weeks"]["2026-11-09"]["mode"], "automatic")

    def test_single_field_persists_across_auto_recalculation(self):
        raw = source()
        key = game_key(G1)
        start, record = make_record(raw, "partial", {"changes": {key: {"guest_cabin": "4"}}}, NOW)
        store = {"schema_version": 1, "weeks": {start: record}}
        raw["games"][0]["home_cabin"] = "2"
        raw["games"][0]["guest_cabin"] = "3"
        plan = effective_plan(raw, store, NOW)
        self.assertEqual(plan["games"][0]["guest_cabin"], "4")
        self.assertEqual(plan["games"][0]["home_cabin"], "2")
        self.assertTrue(plan["games"][0]["manual_override"])
        self.assertEqual(plan["games"][1]["guest_cabin"], "4")

    def test_ambiguous_fixture_is_not_silently_overridden(self):
        raw = source()
        key = game_key(G1)
        _, record = make_record(raw, "partial", {"changes": {key: {"guest_cabin": "1"}}}, NOW)
        raw["games"].insert(1, copy.deepcopy(G1))
        plan = effective_plan(raw, {"weeks": {"2026-11-09": record}}, NOW)
        self.assertEqual(plan["manual_weeks"]["2026-11-09"]["unmatched"], 1)
        self.assertEqual(plan["games"][0]["guest_cabin"], "3")
        self.assertEqual(plan["games"][1]["guest_cabin"], "3")

    def test_rescheduled_fixture_is_flagged_not_assigned_to_another(self):
        raw = source()
        key = game_key(G1)
        _, record = make_record(raw, "partial", {"changes": {key: {"guest_cabin": "1"}}}, NOW)
        raw["games"][0]["date"] = "2026-11-15"
        plan = effective_plan(raw, {"weeks": {"2026-11-09": record}}, NOW)
        self.assertEqual(plan["manual_weeks"]["2026-11-09"]["unmatched"], 1)
        self.assertEqual(plan["games"][0]["guest_cabin"], "3")

    def test_locked_week_freezes_games_but_not_other_weeks(self):
        raw = source()
        edited = [copy.deepcopy(G1), copy.deepcopy(G2)]
        edited[0]["guest_cabin"] = "4"
        edited[1]["time"] = "12:00"
        edited.append(dict(G1, time="17:00", away="Zusätzlicher Gegner"))
        _, record = make_record(raw, "locked", {"games": edited}, NOW)
        store = {"weeks": {"2026-11-09": record}}
        raw["games"][0]["guest_cabin"] = "3"
        raw["games"].append(dict(G1, time="13:00", away="Nicht übernehmen"))
        plan = effective_plan(raw, store, NOW)
        current = [g for g in plan["games"] if g["date"] == "2026-11-14"]
        self.assertEqual(len(current), 3)
        self.assertEqual(current[0]["guest_cabin"], "4")
        self.assertEqual(current[1]["time"], "12:00")
        self.assertTrue(all(g["manual_override"] for g in current))
        self.assertEqual(plan["games"][-1]["away"], G3["away"])

    def test_expiration_does_not_apply_old_week(self):
        raw = source()
        _, record = make_record(raw, "locked", {"games": []}, NOW)
        store = {"weeks": {"2026-11-09": record}}
        next_week = datetime(2026, 11, 17, 12, 0, tzinfo=ZoneInfo("Europe/Berlin"))
        plan = effective_plan(raw, store, next_week)
        self.assertEqual(len(plan["games"]), 3)
        self.assertEqual(plan["manual_weeks"]["2026-11-09"]["mode"], "automatic")

    def test_unlock_removes_record(self):
        start, record = make_record(source(), "automatic", {}, NOW)
        self.assertEqual(start, "2026-11-09")
        self.assertIsNone(record)

    def test_validation_rejects_invalid_keys_and_dates(self):
        with self.assertRaises(ValueError):
            make_record(source(), "partial", {"changes": {"fake": {"home_cabin": "1"}}}, NOW)
        with self.assertRaises(ValueError):
            make_record(source(), "locked", {"games": [dict(G1, date="2026-11-21")]}, NOW)
        with self.assertRaises(ValueError):
            make_record(source(), "locked", {"games": [dict(G1, guest_cabin="<script>")]}, NOW)
        with self.assertRaises(ValueError):
            make_record(source(), "locked", {"games": [dict(G1, festival="not bool")]}, NOW)

    def test_private_fields_are_rejected_for_manual_public_plan(self):
        with self.assertRaises(ValueError):
            clean_game(dict(G1, internal_password="secret"), "2026-11-09", "2026-11-15")

    def test_atomic_save_permissions_backup_and_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "private" / "overrides.json"
            empty = file_revision(path)
            one = {"schema_version": 1, "weeks": {"2026-11-09": {"mode": "partial", "changes": {}}}}
            save_store(one, path)
            self.assertNotEqual(file_revision(path), empty)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(load_store(path), one)
            save_store({"schema_version": 1, "weeks": {}}, path)
            self.assertEqual(json.loads(path.with_suffix(".bak").read_text()), one)


    def test_admin_http_auth_csrf_revision_and_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            src=d/"source.json";src.write_text(json.dumps(source()),encoding="utf-8")
            secret=d/"password";secret.write_text("strong-test-password-123456",encoding="utf-8")
            with socket.socket() as s:
                s.bind(("127.0.0.1", 0)); port=s.getsockname()[1]
            origin=f"http://127.0.0.1:{port}"
            env=dict(os.environ, TUSBERNE_CABINS_SOURCE=str(src), TUSBERNE_CABINS_ADMIN_PASSWORD_FILE=str(secret),
                     TUSBERNE_CABINS_ADMIN_PORT=str(port), TUSBERNE_CABINS_ADMIN_ORIGIN=origin,
                     TUSBERNE_CABINS_OVERRIDES=str(d/"private"/"overrides.json"))
            srv=subprocess.Popen([sys.executable,str(ROOT/"scripts"/"pi_cabins_admin.py")],env=env,
                                 stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                credentials=base64.b64encode(b"kabinen:strong-test-password-123456").decode()
                def request(path, data=None, auth=True, origin_header=True, revision_header=True):
                    headers={}
                    if auth: headers["Authorization"]="Basic "+credentials
                    if data is not None:
                        headers["Content-Type"]="application/json"
                        if revision_header:headers["X-TUSBERNE-EDITOR"]="1"
                        if origin_header:headers["Origin"]=origin
                    rq=Request(origin+path, data=json.dumps(data).encode() if data is not None else None,headers=headers)
                    try:
                        with urlopen(rq,timeout=2) as res:
                            raw=res.read();return res.status,json.loads(raw) if path.startswith("/api/") else raw
                    except HTTPError as e:
                        return e.code,e.read()
                for _ in range(50):
                    if srv.poll() is not None: self.fail("Admin HTTP server failed to start")
                    try:
                        status, data=request("/api/state");break
                    except OSError: time.sleep(.05)
                else: self.fail("Admin HTTP server did not bind")
                self.assertEqual(status, 200)
                self.assertEqual(len(data["auto_games"]), 2)
                self.assertEqual(request("/api/state",auth=False)[0], 401)
                self.assertEqual(request("/",auth=True)[0], 200)
                key=data["game_keys"][0]
                payload={"revision":data["revision"],"mode":"partial","changes":{key:{"guest_cabin":"4"}}}
                self.assertEqual(request("/api/week",payload,origin_header=False)[0],403)
                self.assertEqual(request("/api/week",payload,revision_header=False)[0],403)
                status, result=request("/api/week",payload)
                self.assertEqual(status,200)
                self.assertTrue(result["saved"])
                self.assertEqual(request("/api/week",payload)[0],409)
                status, data=request("/api/state")
                self.assertEqual(data["effective_games"][0]["guest_cabin"],"4")
                payload={"revision":data["revision"],"mode":"locked","games":[]}
                self.assertEqual(request("/api/week",payload)[0],200)
                status, data=request("/api/state")
                self.assertEqual(data["effective_games"],[])
                payload={"revision":data["revision"],"mode":"automatic"}
                self.assertEqual(request("/api/week",payload)[0],200)
                status, data=request("/api/state")
                self.assertEqual(data["mode"],"automatic")
                self.assertEqual(len(data["effective_games"]),2)
            finally:
                srv.terminate()
                try:srv.wait(timeout=2)
                except subprocess.TimeoutExpired:srv.kill()

    def test_html_contains_requested_modes_and_branding(self):
        html = (ROOT / "scripts" / "kabinen_admin.html").read_text()
        for token in ("Einzelne Kabinen überschreiben", "Ganze Woche manuell sperren", "Änderungen speichern", "EINMAL BERNE IMMER BERNE", "tus BERNE"):
            self.assertIn(token, html)


if __name__ == "__main__":
    unittest.main()