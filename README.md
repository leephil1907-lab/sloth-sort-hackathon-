# Sloth Sort 🦥

**A slow, local, open-source file tidier.** Point it at a messy folder; an open-weight
model running on *your* machine decides where each file belongs; the sloth moves a few
files, takes a nap, moves a few more. It never deletes, never overwrites, and every run
can be undone.

Built for the *Slow and Steady* challenge (International Sloth Day) — see
[`SUBMISSION.md`](./SUBMISSION.md) for the write-up.

## Why "sloth"?

- `--pace N` — never handles more than N files per shift (default 10)
- `--siesta SECONDS` — rests between files
- `watch --nap 6h` — works short shifts, sleeps for hours, repeats forever
- junk is **archived**, never deleted — sloths conserve, they don't destroy
- dry-run by default; `undo` reverses the last run from the manifest

## Stack

| Piece | Role | License |
|---|---|---|
| [Ollama](https://github.com/ollama/ollama) | local model server (`/api/generate`) on 127.0.0.1 | MIT |
| `qwen2.5:0.5b-instruct` | the classifier brain (397 MB, CPU-only is fine) | Apache-2.0 |
| `sloth_sort.py` (~450 LOC) | the agent loop: sniff → classify → move → log | MIT |

No cloud. No API keys. No subscription. The harness is stdlib-only (`urllib`);
`pypdf` is optional for reading PDF text.

## Quickstart

```bash
# 1. install Ollama and pull the (~400 MB) model  → then internet can go off forever
ollama pull qwen2.5:0.5b-instruct

# 2. make a demonic little mess and look at it
python3 make_mess.py demo/messy_downloads

# 3. dry run — the default, nothing moves
python3 sloth_sort.py scan demo/messy_downloads --pace 24

# 4. actually tidy (small shifts, like a sloth)
python3 sloth_sort.py apply demo/messy_downloads --pace 8 --siesta 1

# 5. regret nothing
python3 sloth_sort.py undo demo/messy_downloads

# 6. put it on night shift — file 8 things, nap 6 hours, repeat
python3 sloth_sort.py watch ~/Downloads --pace 8 --nap 6h

# 7. or make it fully hands-free with cron (02:00 nightly):
# 0 2 * * * cd ~/sloth-sort && python3 sloth_sort.py apply "$HOME/Downloads" --pace 8 --siesta 2 >> "$HOME/.slothsort-nightly.log" 2>&1
```

(For cron, keep `ollama serve` running at boot — systemd user service or launchd —
and it never needs a network or a thought again.)

Natural-language owner rules work too:

```bash
python3 sloth_sort.py scan ~/Downloads --instructions "anything about taxes goes to Finance, keep leases under Documents"
```

Swap the brain without changing the harness — any model your server has:

```bash
python3 sloth_sort.py scan ~/Downloads --model qwen2.5:1.5b-instruct   # smarter, still local
python3 sloth_sort.py scan ~/Downloads --model llama3.2:1b
```

## Safety guarantees

1. **Dry-run first.** `scan` is the default verb; reviewing the plan costs you nothing.
2. **Never deletes.** The model can only *suggest* archiving; files go to `_archive/`.
3. **Never overwrites.** Name collisions get `-2`, `-3` suffixes.
4. **Undo.** Every move is appended to `.slothsort/manifest.jsonl`; `undo` reverses
   the last run in exact reverse order.
5. **Skips carefully.** Hidden files, symlinks, and its own output folders are ignored.
6. **Guard rails.** Categories are a closed list; anything out-of-vocabulary falls back
   to an extension-based rule, and the run keeps going — a sloth never crashes.

## Demo

`demo/` contains the logs from a real run over `make_mess.py`'s 24-file mess:
`02_dryrun_final.log`, `03_apply.log`, `05_final_apply.log`. Zero human edits —
that is genuinely qwen2.5:0.5b doing taxonomy on 2 CPU cores at ~3 s/file.
