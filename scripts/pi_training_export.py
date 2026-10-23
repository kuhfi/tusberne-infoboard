#!/usr/bin/env python3
"""Extract public training schedules from the Pi's existing Drive HTML files.

Default: read-only preview. --apply updates ONLY the GitHub working copy's
data/training-{berne,farmsen}.json, without git commit or push. The Pi display
and the original HTML files are never modified.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PI_TILES = Path("/home/kuhfi/infoboard-app/public/portrait-content")
LOCATIONS = {
    "berne": ("01 Trainingsplan Berne.html", "Berner Allee"),
    "farmsen": ("02 Trainingsplan Farmsen.html", "3 für FARBE"),
}
WEEKDAYS = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag")
MAX_HTML_SIZE = 12 * 1024 * 1024


class Node:
    def __init__(self, tag, attrs=()):
        self.tag = tag
        self.attrs = dict(attrs)
        self.children = []


class DOM(HTMLParser):
    """Small DOM for the HTML *schedule*, excluding the large embedded logo."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in {"br", "img", "meta", "link", "hr", "input"}:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, attrs))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def has_class(element, name):
    return isinstance(element, Node) and name in element.attrs.get("class", "").split()


def children(parent, tag, classname=None):
    return [
        ch for ch in parent.children
        if isinstance(ch, Node) and ch.tag == tag
        and (classname is None or has_class(ch, classname))
    ]


def one(values, description):
    if len(values) != 1:
        raise ValueError(f"Trainingsplan-Struktur ungueltig: {description}")
    return values[0]


def node_text(node):
    if isinstance(node, str):
        return node
    if node.tag == "br":
        return " "
    prefix = " " if node.tag == "small" else ""
    return prefix + "".join(node_text(ch) for ch in node.children)


def clean_text(node):
    return " ".join(node_text(node).split())


def parse_schedule(raw, location_id):
    if location_id not in LOCATIONS:
        raise ValueError("Unbekannter Trainingsplatz")
    if not isinstance(raw, str):
        raise ValueError("HTML-Datei ist kein Text")

    # Header is before a ~5 MB embedded logo. Match metadata without copying it.
    head = re.search(
        r'<div class="brandtext">\s*<h1>(.*?)</h1>\s*'
        r'<div class="sub">\s*<span>(.*?)</span>',
        raw, flags=re.DOTALL
    )
    if not head:
        raise ValueError("Trainingsplan-Kopfzeile fehlt")
    location = unescape(re.sub(r"<[^>]+>", "", head.group(1))).strip()
    season = unescape(re.sub(r"<[^>]+>", "", head.group(2))).strip()
    if LOCATIONS[location_id][1] not in location or not re.fullmatch(r"Saison \d{4}/\d{2}", season):
        raise ValueError("Trainingsplan-Platz oder Saison unerwartet")

    start = raw.find('<div class="week">')
    if start < 0:
        raise ValueError("Trainingsplan-Wochenbereich fehlt")
    end = raw.find("</main>", start)
    if end < 0 or end - start > 200_000:
        raise ValueError("Trainingsplan-Wochenbereich unvollstaendig")
    dom = DOM()
    dom.feed(raw[start:end])
    week = one(children(dom.root, "div", "week"), "Woche")
    days = []

    for day in children(week, "section", "day"):
        name = day.attrs.get("aria-label", "")
        blocks = []
        for row in children(day, "div", "row"):
            t = one(children(row, "div", "time"), "Zeitspalte")
            block_label = clean_text(one(
                [s for s in children(t, "span") if not has_class(s, "hours")],
                "Blocknummer"
            ))
            hours = clean_text(one(children(t, "span", "hours"), "Uhrzeit"))
            front = one(
                [h for h in children(row, "div", "half") if has_class(h, "front")],
                "Vorne"
            )
            back = one(
                [h for h in children(row, "div", "half") if has_class(h, "back")],
                "Hinten"
            )
            if not re.fullmatch(r"Block [1-3]", block_label) or not hours or len(hours) > 60:
                raise ValueError("Trainingsblock oder Uhrzeit ungueltig")
            f = [clean_text(c) for c in children(front, "div", "cell")]
            b = [clean_text(c) for c in children(back, "div", "cell")]
            if not f or not b:
                raise ValueError("Trainingsblock ohne Platzzuordnung")
            if any(len(value) > 150 for value in f + b):
                raise ValueError("Unerwartet langer Mannschaftsname")
            blocks.append({"block": block_label, "time": hours, "front": f, "back": b})

        if len(blocks) != 3 or [b["block"] for b in blocks] != ["Block 1", "Block 2", "Block 3"]:
            raise ValueError(f"Unvollstaendige Trainingsbloecke fuer {name}")
        days.append({"name": name, "blocks": blocks})

    if [day["name"] for day in days] != list(WEEKDAYS):
        raise ValueError("Trainingstage fehlen oder sind vertauscht")
    return {"schema_version": 1, "location_id": location_id,
            "location": location, "season": season, "days": days}


def export_one(local_root, location_id):
    file_name, _ = LOCATIONS[location_id]
    source = local_root / "kachel1" / file_name
    if source.is_symlink() or not source.is_file():
        raise ValueError("Trainingsplan fehlt: " + file_name)
    stat = source.stat()
    if stat.st_size <= 0 or stat.st_size > MAX_HTML_SIZE:
        raise ValueError("Trainingsplan-Dateigroesse unerwartet: " + file_name)
    parsed = parse_schedule(source.read_text(encoding="utf-8"), location_id)

    target = REPO / f"data/training-{location_id}.json"
    previous = json.loads(target.read_text(encoding="utf-8")) if target.is_file() else None
    modified = datetime.fromtimestamp(
        stat.st_mtime_ns // 1_000_000 / 1000, timezone.utc
    ).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    previous_content = (
        {k: v for k, v in previous.items() if k != "source_modified_at"}
        if isinstance(previous, dict) else None
    )
    # Don't create commits just because the source file timestamp changed.
    if previous_content == parsed and previous.get("source_modified_at"):
        modified = previous["source_modified_at"]
    new = {**{k: parsed[k] for k in ("schema_version", "location_id", "location", "season")},
           "source_modified_at": modified, "days": parsed["days"]}
    contents = (json.dumps(new, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return target, contents, previous != new


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-root", type=Path, default=PI_TILES)
    parser.add_argument("--apply", action="store_true",
                        help="Update only the local GitHub copy; no commit or push")
    args = parser.parse_args()
    try:
        staged = [export_one(args.local_root, site) for site in LOCATIONS]
        for target, data, changed in staged:
            print(f"{target.name}: " + ("Aktualisierung" if changed else "unveraendert"))
        if args.apply:
            for target, data, changed in staged:
                if changed:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
            print("JSON-Trainingsplaene vorbereitet. Noch KEIN Git-Push.")
        else:
            print("Probelauf: keine Dateien veraendert.")
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        print("STOPP: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
