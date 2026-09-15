#!/usr/bin/env python3
"""Scans a folder of markdown notes and writes viewer/graph-data.js.

Standard library only. Run: python3 build.py [notes-folder]
"""
import json
import os
import re
import sys

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)")
EXCERPT_LEN = 700


def strip_markdown(text: str) -> str:
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = WIKILINK_RE.sub(lambda m: m.group(1), text)
    text = re.sub(r"\[\[|\]\]", "", text)
    text = re.sub(r"[*_`>]", "", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text.strip()


def find_notes(root: str):
    notes = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for fname in sorted(filenames):
            if not fname.lower().endswith(".md"):
                continue
            full_path = os.path.join(dirpath, fname)
            rel_dir = os.path.relpath(dirpath, root)
            group = "notes" if rel_dir == "." else rel_dir.split(os.sep)[0]
            title = os.path.splitext(fname)[0]
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                raw = f.read()
            notes.append(
                {
                    "path": full_path,
                    "title": title,
                    "group": group,
                    "raw": raw,
                }
            )
    return notes


def build_graph(notes):
    nodes = []
    for i, note in enumerate(notes):
        clean = strip_markdown(note["raw"])
        excerpt = clean[:EXCERPT_LEN]
        nodes.append(
            {
                "id": i,
                "label": note["title"],
                "group": note["group"],
                "excerpt": excerpt,
                "path": note["path"],
            }
        )

    title_to_id = {n["label"].lower(): n["id"] for n in nodes}
    links = []
    seen_pairs = set()

    for i, note in enumerate(notes):
        raw_lower = note["raw"].lower()
        targets = set()

        for m in WIKILINK_RE.finditer(note["raw"]):
            linked_title = m.group(1).strip().lower()
            if linked_title in title_to_id:
                targets.add(title_to_id[linked_title])

        for other in nodes:
            if other["id"] == i:
                continue
            if other["label"].lower() in raw_lower:
                targets.add(other["id"])

        for target in targets:
            pair = tuple(sorted((i, target)))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            links.append({"source": pair[0], "target": pair[1]})

    return {"nodes": nodes, "links": links}


def main():
    notes_dir = sys.argv[1] if len(sys.argv) > 1 else "./notes"

    if not os.path.isdir(notes_dir) or not find_notes(notes_dir):
        print(f"No markdown notes found in {notes_dir!r} — nothing to build.")
        sys.exit(1)

    notes = find_notes(notes_dir)
    graph = build_graph(notes)

    os.makedirs("viewer", exist_ok=True)
    out_path = os.path.join("viewer", "graph-data.js")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("const GRAPH = ")
        f.write(json.dumps(graph, indent=2))
        f.write(";\n")

    print(f"Scanned {len(notes)} notes in {notes_dir!r}")
    print(f"Wrote {len(graph['nodes'])} nodes and {len(graph['links'])} links to {out_path}")


if __name__ == "__main__":
    main()
