#!/usr/bin/env python3
"""
Sloth Sort 🦥  —  a slow, local, open-source file tidier.

Point it at your mess (Downloads, Desktop, a shared drive) and it asks an
open-weight model running *on your machine* how each file should be filed,
then lazily moves them — a few at a time — into tidy folders.

Why sloth? Because it:
  - works in small batches (--pace), with long naps between them (--watch --nap)
  - never deletes anything, ever (junk is *archived*, not removed)
  - never overwrites, and writes an undo manifest so you can reverse a whole run
  - runs on coffee-stained hardware with no internet and no subscription

Requires: a local Ollama (or any server speaking the same /api/generate API)
with a small open-weight instruct model, e.g.  qwen2.5:0.5b-instruct

    python3 sloth_sort.py scan ~/Downloads            # dry run, the default
    python3 sloth_sort.py apply ~/Downloads --pace 8  # move at most 8 files
    python3 sloth_sort.py undo ~/Downloads            # reverse the last run
    python3 sloth_sort.py watch ~/Downloads --nap 6h  # slow & steady, forever
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# config

DEFAULT_MODEL = os.environ.get("SLOTH_MODEL", "qwen2.5:0.5b-instruct")
DEFAULT_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
META_DIR = ".slothsort"
ARCHIVE_DIR = "_archive"
SNIPPET_LIMIT = 1200

CATEGORIES = [
    "Finance",     # receipts, invoices, statements, taxes
    "Documents",   # contracts, letters, resumes, official papers
    "Notes",       # notes, todo lists, study notes, recipes
    "Photos",      # photographs, camera imports
    "Screenshots", # screenshots, screen recordings
    "Code",        # source, scripts, configs, dev logs
    "Media",       # music, video, audio, memes
    "Software",    # installers, disk images, executables
    "Personal",    # credentials, IDs, medical, private records
    "Junk",        # temp files, caches, empty stubs
]

TEXT_EXTS = {
    ".txt", ".md", ".rst", ".log", ".csv", ".tsv", ".json", ".yaml",
    ".yml", ".xml", ".html", ".htm", ".py", ".js", ".ts", ".java",
    ".c", ".h", ".cpp", ".go", ".rs", ".rb", ".php", ".sql", ".ini",
    ".cfg", ".toml", ".sh",
}

# last-resort, no-model classifications (sloth always has a plan B)
EXT_FALLBACK = {
    "Photos": {".jpg", ".jpeg", ".png", ".heic", ".gif", ".webp", ".raw"},
    "Media": {".mp4", ".mkv", ".mov", ".mp3", ".wav", ".flac", ".m4a"},
    "Software": {".dmg", ".pkg", ".exe", ".msi", ".deb", ".appimage", ".iso"},
    "Code": {".py", ".js", ".ts", ".go", ".rs", ".java", ".c", ".cpp",
             ".h", ".rb", ".php", ".sql", ".sh", ".html", ".css"},
    "Junk": {".tmp", ".cache", ".part", ".download", ".crdownload"},
}

# ---------------------------------------------------------------------------
# model access

PROMPT = """You are a meticulous file organizer. Classify ONE file into exactly one category and give it a clean, descriptive filename.

Categories and what belongs in them:
- Finance: receipts, invoices, bank statements, taxes, budgets
- Documents: contracts, letters, resumes, agreements, official papers
- Notes: notes, journals, todo lists, study notes, recipes
- Photos: photographs and camera imports (names like IMG_, DSC, PXL)
- Screenshots: screenshots and screen recordings
- Code: source code, scripts, configs, developer logs
- Media: music, video, audio, memes
- Software: installers, disk images, executables
- Personal: credentials, password exports/backups, API keys, IDs, medical, private records
- Junk: temp files, caches, zero-content stubs, "copy of copy" duplicates

Rules:
1. Answer with ONLY a single JSON object. No prose, no markdown fences.
2. "filename": descriptive, lowercase, words joined with hyphens, max 50 chars before the extension, MUST keep the original extension.
3. "archive": true only if the file is junk or obsolete (temp, cache, ancient duplicate).
4. The category MUST be Personal whenever the filename or content mentions passwords, credentials, secrets, API keys, vault exports, or ID numbers — even if it looks like a document, note, or code/config file.
5. Leases, tenancy agreements, rental agreements and letters to a landlord are Documents, never Finance. Recipes and study/lecture material are Notes. Developer .log dumps and crash/error logs are Junk (archive them).
6. "reason": at most 10 words.

Examples:
file: IMG_8102.PNG | type: image | size: 3.1 MB
{{"category":"Photos","filename":"img-8102.png","archive":false,"reason":"camera photo, classify by filename"}}

file: receipt_oct_ark_cafe.pdf | type: document | size: 42 KB | content: "ARK CAFE 12/10/2025 flat white x2 6.00 total 6.00 THANK YOU"
{{"category":"Finance","filename":"ark-cafe-october-receipt.pdf","archive":false,"reason":"cafe receipt"}}

file: tmp9F31.tmp | type: unknown | size: 2 KB
{{"category":"Junk","filename":"tmp9f31.tmp","archive":true,"reason":"temporary file"}}

file: go live checklist.txt | type: text | size: 1 KB | content: "launch plan - draft marketing email - freeze code Friday"
{{"category":"Notes","filename":"go-live-checklist-notes.txt","archive":false,"reason":"planning notes"}}

file: vault_backup_2018.txt | type: text | size: 2 KB | content: "old password export: site,login,password(old) forums.example hunter22"
{{"category":"Personal","filename":"vault-backup-2018-personal.txt","archive":true,"reason":"old credentials export, archive safely"}}

file: tenancy_agreement_v2.pdf | type: document | size: 96 KB | content: "RESIDENTIAL TENANCY AGREEMENT Property: Flat 4B Tenant: A. Bala Monthly rent: 200,000 NGN"
{{"category":"Documents","filename":"tenancy-agreement.pdf","archive":false,"reason":"lease documents, not finance"}}

file: jollof_rice_recipe.md | type: text | size: 1 KB | content: "# Party Jollof - 4 cups rice - 6 bell peppers + 2 scotch bonnets blended"
{{"category":"Notes","filename":"party-jollof-recipe-notes.md","archive":false,"reason":"recipe notes"}}

file: crash_20251009.log | type: text | size: 4 KB | content: "2025-10-09 22:41:57 segfault at 0x7ff stack trace frame 0: module=worker"
{{"category":"Junk","filename":"crash-20251009.log","archive":true,"reason":"stale crash log"}}

Now classify this file.
{user_rules}file: {name} | type: {kind} | size: {size}{content}
JSON answer:"""


def query_model(host: str, model: str, name: str, kind: str, size: str,
                content: str, user_rules: str, timeout: int) -> dict:
    """Ask the local model how to file one file. Returns raw text."""
    prompt = PROMPT.format(
        user_rules=f"Extra owner rules: {user_rules}\n" if user_rules else "",
        name=name, kind=kind, size=size,
        content=f' | content: "{content}"' if content else "",
    )
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.0,
            "num_predict": 160,
            "num_ctx": 3072,
            "num_thread": os.cpu_count() or 2,
        },
    }).encode()
    req = urllib.request.Request(
        host.rstrip("/") + "/api/generate", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        payload = json.loads(r.read().decode())
    meta = {
        "eval_ms": payload.get("eval_duration", 0) // 1_000_000,
        "eval_count": payload.get("eval_count", 0),
    }
    return {"raw": payload.get("response", ""), **meta}


# ---------------------------------------------------------------------------
# content sniffing

def human_size(n: int) -> str:
    f = float(n)
    for unit in ["B", "KB", "MB", "GB"]:
        if f < 1024 or unit == "GB":
            return f"{f:.0f} {unit}" if unit == "B" else f"{f:.1f} {unit}"
        f /= 1024
    return f"{n} B"


def sniff(p: Path) -> tuple[str, str]:
    """Return (kind, content_snippet). Best effort, stdlib-only."""
    ext = p.suffix.lower()
    if ext in TEXT_EXTS:
        try:
            txt = p.read_text(errors="replace")[:SNIPPET_LIMIT]
            txt = re.sub(r"\s+", " ", txt).strip()
            return "text", txt
        except OSError:
            return "text", ""
    if ext == ".pdf":
        try:
            import pypdf  # type: ignore
            reader = pypdf.PdfReader(str(p))
            txt = " ".join(
                (reader.pages[i].extract_text() or "") for i in range(min(2, len(reader.pages)))
            )
            txt = re.sub(r"\s+", " ", txt or "").strip()
            return "document", txt[:SNIPPET_LIMIT]
        except Exception:
            return "document", ""
    if ext == ".docx":
        try:
            with zipfile.ZipFile(p) as z:
                xml = z.read("word/document.xml").decode("utf-8", "replace")
            txt = re.sub(r"<[^>]+>", " ", xml)
            txt = re.sub(r"\s+", " ", txt).strip()
            return "document", txt[:SNIPPET_LIMIT]
        except Exception:
            return "document", ""
    if ext in {".jpg", ".jpeg", ".png", ".heic", ".gif", ".webp", ".raw"}:
        return "image", ""
    if ext in {".mp4", ".mkv", ".mov", ".mp3", ".wav", ".flac", ".m4a"}:
        return "media", ""
    if ext in {".dmg", ".pkg", ".exe", ".msi", ".deb", ".appimage", ".iso"}:
        return "software", ""
    return "unknown", ""


# ---------------------------------------------------------------------------
# parsing & fallback

def parse_answer(raw: str) -> dict | None:
    """Tolerant JSON extraction: model output may include stray text."""
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    blob = m.group(0)
    blob = re.sub(r",\s*(\})", r"\1", blob)  # trailing commas
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        cat = re.search(r'"category"\s*:\s*"([^"]+)"', blob)
        fil = re.search(r'"filename"\s*:\s*"([^"]+)"', blob)
        if not (cat and fil):
            return None
        data = {"category": cat.group(1), "filename": fil.group(1),
                "archive": '"archive": true' in blob, "reason": "recovered parse"}
    if not isinstance(data, dict) or "category" not in data or "filename" not in data:
        return None
    return data


def fallback(p: Path, size: int) -> dict:
    """No-model heuristic. The sloth always lands on its feet."""
    ext = p.suffix.lower()
    name = p.name.lower()
    cat = "Documents"
    if "screenshot" in name or "screen recording" in name:
        cat = "Screenshots"
    elif size == 0:
        cat = "Junk"
    else:
        for c, exts in EXT_FALLBACK.items():
            if ext in exts:
                cat = c
                break
    return {"category": cat, "filename": slug(p.name), "archive": cat == "Junk",
            "reason": "fallback rule (model unavailable)"}


def slug(name: str) -> str:
    stem, dot, ext = name.rpartition(".")
    if not stem:                      # no extension present
        stem, dot, ext = name, "", ""
    stem = unicodedata.normalize("NFKD", stem)
    stem = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower()
    stem = re.sub(r"-{2,}", "-", stem)[:50].strip("-") or "unnamed"
    return stem + (dot + ext.lower() if dot else "")


# ---------------------------------------------------------------------------
# the agent loop

def list_candidates(root: Path) -> list[Path]:
    keep = set(CATEGORIES) | {ARCHIVE_DIR, META_DIR}
    out = []
    for p in sorted(root.iterdir()):
        if p.name.startswith(".") or p.is_dir() and p.name in keep:
            continue
        if p.is_file() and not p.is_symlink():
            out.append(p)
    return out


def decide(root: Path, p: Path, host: str, model: str, user_rules: str,
           siesta: float, timeout: int) -> dict:
    kind, content = sniff(p)
    size = p.stat().st_size
    time.sleep(siesta)                # little rest between files — conserve energy
    ans = {"via": "model"}
    try:
        out = query_model(host, model, p.name, kind, human_size(size),
                          content, user_rules, timeout)
        data = parse_answer(out["raw"])
        if data is None:
            data = fallback(p, size)
            ans["via"] = "fallback(parse-fail)"
        else:
            ans["via"] = "model"
            ans["eval_ms"] = out["eval_ms"]
            if data.get("category") not in CATEGORIES:      # guard rail
                data["category"] = fallback(p, size)["category"]
            data["filename"] = slug(str(data["filename"]))
    except (urllib.error.URLError, TimeoutError, OSError):
        data = fallback(p, size)
        ans["via"] = "fallback(no-server)"
    base_ext = p.suffix.lower()
    if not data["filename"].lower().endswith(base_ext):
        data["filename"] += base_ext
    ans.update(data)
    return ans


def unique_path(dst: Path) -> Path:
    if not dst.exists():
        return dst
    stem, suffix = dst.stem, dst.suffix
    n = 2
    while True:
        cand = dst.with_name(f"{stem}-{n}{suffix}")
        if not cand.exists():
            return cand
        n += 1


def plan_and_act(root: Path, pace: int, apply: bool, host: str, model: str,
                 user_rules: str, siesta: float, timeout: int,
                 quiet: bool = False) -> list[dict]:
    files = list_candidates(root)[:pace]
    if not files:
        print("🦥 Nothing to sort. The sloth goes back to sleep.")
        return []
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = root / META_DIR / "manifest.jsonl"
    moves, rows = [], files
    for p in rows:
        d = decide(root, p, host, model, user_rules, siesta, timeout)
        folder = ARCHIVE_DIR if d["archive"] else d["category"]
        dst = unique_path(root / folder / d["filename"])
        moves.append({**d, "run_id": run_id, "src": str(p), "dst": str(dst),
                      "folder": folder})
        print(f"  {p.name:<42} → {folder}/{dst.name}")
        print(f"      ↳ [{d['via']}] {d['reason']}")
    if apply:
        log_path.parent.mkdir(exist_ok=True)
        for mv in moves:
            target = Path(mv["dst"])
            target.parent.mkdir(exist_ok=True)
            shutil.move(mv["src"], target)
            with log_path.open("a") as fh:
                fh.write(json.dumps(mv) + "\n")
        print(f"\n🦥 Moved {len(moves)} file(s). Manifest appended — `undo` works.")
    else:
        print(f"\n🦥 DRY RUN — nothing moved. Rerun with: apply")
    return moves


# ---------------------------------------------------------------------------
# undo & watch

def undo(root: Path) -> None:
    log_path = root / META_DIR / "manifest.jsonl"
    if not log_path.exists():
        print("🦥 Nothing to undo (no manifest).")
        return
    entries = [json.loads(l) for l in log_path.read_text().splitlines() if l.strip()]
    if not entries:
        print("🦥 Nothing to undo (empty manifest).")
        return
    last_run = entries[-1]["run_id"]
    undone = [e for e in entries if e["run_id"] != last_run]
    count = 0
    for e in reversed([e for e in entries if e["run_id"] == last_run]):
        src, dst = Path(e["dst"]), Path(e["src"])
        if src.exists() and not dst.exists():
            shutil.move(str(src), str(dst))
            count += 1
    log_path.write_text("".join(json.dumps(e) + "\n" for e in undone))
    print(f"🦥 Undid run {last_run}: {count} file(s) back home.")


def parse_nap(s: str) -> float:
    """Accepts seconds ('300'), minutes ('30m'), hours ('6h')."""
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([smh]?)", s)
    if not m:
        raise argparse.ArgumentTypeError(f"bad nap duration: {s}")
    mult = {"": 1, "s": 1, "m": 60, "h": 3600}[m.group(2)]
    return float(m.group(1)) * mult


def watch(args) -> None:
    root = Path(args.folder).expanduser().resolve()
    print(f"🦥 Sloth on duty: {root}")
    print(f"   pace={args.pace} files/nap, napping {args.nap:g}s between shifts, model={args.model}")
    while True:
        n = plan_and_act(root, args.pace, True, args.host, args.model,
                         args.instructions, args.siesta, args.timeout)
        n = len(n)
        if n == 0:
            print(f"   folder is tidy. zzz for {args.nap:g}s…")
        else:
            print(f"   shift over — {n} file(s) filed. zzz for {args.nap:g}s…")
        time.sleep(args.nap)


# ---------------------------------------------------------------------------
# cli

def main() -> None:
    ap = argparse.ArgumentParser(
        prog="sloth_sort", description="🦥 Slow, local, open-source file tidier.")
    ap.add_argument("command", choices=["scan", "apply", "undo", "watch"],
                    help="scan=dry-run (default, safe) · apply=actually move · undo=reverse last run")
    ap.add_argument("folder", help="the mess to tidy (scanned top-level only)")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help=f"open-weight model on your Ollama server (default: {DEFAULT_MODEL})")
    ap.add_argument("--host", default=DEFAULT_HOST,
                    help=f"Ollama-compatible server (default: {DEFAULT_HOST})")
    ap.add_argument("--pace", type=int, default=10,
                    help="max files per run — sloths never rush (default: 10)")
    ap.add_argument("--siesta", type=float, default=1.0,
                    help="seconds of rest between files (default: 1)")
    ap.add_argument("--nap", type=parse_nap, default=3600.0,
                    help="watch mode: rest between shifts, e.g. 300, 30m, 6h (default: 1h)")
    ap.add_argument("--instructions", default="",
                    help="extra owner rules in plain English, e.g. 'keep all leases under Documents'")
    ap.add_argument("--timeout", type=int, default=180,
                    help="per-file model timeout, seconds (default: 180)")
    args = ap.parse_args()

    root = Path(args.folder).expanduser().resolve()
    if not root.is_dir():
        ap.error(f"not a folder: {root}")
    if args.command == "undo":
        undo(root)
        return
    if args.command == "watch":
        watch(args)
        return
    if args.command == "scan":
        print(f"🦥 Sloth Sort — dry run on {root} (model: {args.model})")
        plan_and_act(root, args.pace, False, args.host, args.model,
                     args.instructions, args.siesta, args.timeout)
    else:  # apply
        print(f"🦥 Sloth Sort — APPLYING on {root} (model: {args.model})")
        plan_and_act(root, args.pace, True, args.host, args.model,
                     args.instructions, args.siesta, args.timeout)


if __name__ == "__main__":
    main()
