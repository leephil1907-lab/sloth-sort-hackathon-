---
title: Sloth Sort 🦥 — a local, open-weight file tidier that works while you nap
published: false
tags: devchallenge, hf26challenge
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 3: Slow and Steady](https://dev.to/challenges/hacktoberfest-week3-2026-10-19)*

<!-- Upload images/hero.png (the banner in the repo) via the editor toolbar and paste it right here as the cover image. -->

## What I Built

**Don't sort your Downloads folder. Outsource it to a sloth.**

My `todo list.txt` had carried the item *"sort downloads folder (lol, never)"* for years. So I hired an animal with the correct energy policy: **a local file-tidying agent whose brain is a 397 MB open-weight model** (Qwen2.5-0.5B-Instruct, Apache-2.0) served by **Ollama (MIT)** on my own machine.

Point it at any messy folder. It reads each file — real text extraction for PDFs, DOCX, notes, CSVs, JSON; filename-only for photos and media — asks the local model where it belongs and what a decent name would be, then files everything into tidy per-topic folders. In small shifts: eight files, a siesta, eight more.

The sloth design spec:

- **`--pace 8`** — never moves more than N files per shift
- **`--siesta 2`** — rests between files, like a professional
- **`watch --nap 6h`, or cron** — short night shifts, forever
- **Archive, never delete** — junk is parked in `_archive/`; deleting is a decision the sloth refuses to make
- **Dry-run first, `undo` always** — every run writes a manifest and can be fully reversed

Who gets to be lazier? Me, obviously — but also anyone whose "Downloads" is a geological record, searching receipts with Spotlight at 11pm. The whole thing costs them nothing, needs no internet, and never sends a single byte of their files anywhere.

## Demo

This is a real, unedited run. I built a synthetic-but-painfully-true mess (`make_mess.py`, included): 24 files with real PDFs, a real DOCX, camera imports, temp junk — and, deliberately, two files you'd never want to leave your machine.

**Before:**

```
1password-backup-2019.txt     invoice_INV-2204_final_FINAL (2).pdf
IMG_8102.PNG                  jollof recipe grandma.md
PXL_20250914_181204.jpg       letter to landlord.docx
Screenshot 2025-10-02 .png    rental_agreement_signed.pdf
api_keys_OLD_ROTATED.json     tax_summary_2024.pdf
bank_statement_sept.csv       tmp9F31.tmp
data_pipeline.py              tsdump_error_20251009.log …(24 total)
```

**Dry-run (it's the default verb — you review the plan before anything moves):**

```
$ python3 sloth_sort.py scan demos/messy_downloads --pace 24
  1password-backup-2019.txt        → _archive/1password-backup-2019.txt
      ↳ stale password export, archive safely
  api_keys_OLD_ROTATED.json        → _archive/api-keys-old-rotated.json
      ↳ old credentials export, archive safely
  rental_agreement_signed.pdf      → Documents/rental-agreement-signed.pdf
      ↳ rental agreement signed, not finance
  tax_summary_2024.pdf             → Finance/tax-summary-2024.pdf
      ↳ personal income tax summary
  tmp9F31.tmp                      → _archive/tmp9f31.tmp
      ↳ temporary file
  … (24/24 classified by the model, zero fallbacks)
```

**After `apply`:**

```
Finance/{ark-cafe-october-receipt, bank-statement-sept, invoice-…, tax-summary-2024}
Documents/{letter-to-landlord.docx, rental-agreement-signed.pdf, jollof-recipe-grandma.md}
Notes/{lecture-w4-notes, meeting-notes-monday, todo-list …}
Photos/{img-8102.png, pxl-….jpg, cat-meme-final.jpg}
Screenshots/  Software/  Code/
_archive/{1password-backup-2019.txt, api-keys-old-rotated.json, tmp9f31.tmp}
```

**Undo, verified live:** `🦥 Undid run 20261025-031510: 23 file(s) back home.` — then I re-applied. Full, unedited logs are in the repo under `demo/*.log`.

<!-- Optionally: upload audio/sloth-sort-audio.mp3 here as the narrated walkthrough, or record a quick asciinema/terminal GIF:
     python3 make_mess.py demos/mess && python3 sloth_sort.py scan demos/mess --pace 24 -->

🎧 There's also a 75-second narrated walkthrough (`audio/sloth-sort-audio.mp3` in the repo).

## Code

The whole harness is one dependency-light file (`sloth_sort.py`, ~450 LOC; the only optional pip import is `pypdf` for PDF text). Two excerpts give the flavor.

**The brain conversation** — a 0.5B model is very coachable if you give it a closed category list, strict JSON, and few-shot examples:

```python
PROMPT = """You are a meticulous file organizer. Classify ONE file ...
Categories: Finance, Documents, Notes, Photos, Screenshots, Code, Media, Software, Personal, Junk
Rules: answer with ONLY a single JSON object; filename keeps the original extension;
"archive": true only for junk; if content mentions passwords/credentials/API keys,
the category MUST be Personal; leases and landlord letters are Documents, never Finance.

Example:
file: tenancy_agreement_v2.pdf | content: "RESIDENTIAL TENANCY AGREEMENT ... Monthly rent: 200,000"
{"category":"Documents","filename":"tenancy-agreement.pdf","archive":false,"reason":"lease, not finance"}

Now classify this file.
file: {name} | type: {kind} | size: {size} | content: "{snippet}"
JSON answer:"""
```

**The responsible-part-of-the-sloth loop** — tolerant parsing, closed-list guard rails, manifest logging, no overwrites:

```python
data = parse_answer(raw) or fallback(path, size)          # never crash mid-pile
if data["category"] not in CATEGORIES:                    # closed list, enforced
    data["category"] = fallback(path, size)["category"]
folder = "_archive" if data["archive"] else data["category"]
dst = unique_path(root / folder / slug(data["filename"])) # never overwrite
shutil.move(src, dst)                                     # only after dry-run approval
log_manifest_line(run_id, src, dst)                       # makes `undo` possible
```

{% github leephil1907-lab/sloth-sort-hackathon- %}

Everything else — mess generator, README, logs, hero image, narration — is in the repo:

```
sloth-sort/  sloth_sort.py  make_mess.py  README.md  demo/*.log  images/  audio/
```

## How I Built It

The stack is open all the way down, and the openness is load-bearing:

| Layer | Thing | License | Role |
|---|---|---|---|
| Brain | `qwen2.5:0.5b-instruct`, Q4_K_M, 397 MB | Apache-2.0 | reads each file, returns strict JSON: category, clean filename, archive?, reason |
| Server | Ollama 0.40 on `127.0.0.1:11434` | MIT | serves the GGUF via `/api/generate`; CPU-only, no GPU needed |
| Harness | `sloth_sort.py`, stdlib HTTP client | MIT | agent loop: sniff → classify → (dry-run|move) → manifest |

Built and demoed entirely inside a 2-core cloud sandbox — deliberately weak hardware, because sloths don't need a gym:

- ~**2.5–3 s per file** end-to-end (~35 tokens/s generation on two threads)
- 24-file folder sorted in **~65 s**, including model load
- RAM stayed flat and boring; the model weighs less than the PDFs of some people's tax years

Honest process notes (this took three prompt iterations, and it shows why local iteration matters): **pass 1** leaked a legacy password export into "Documents"; fixed with a hard rule — *anything mentioning credentials is Personal*. **Pass 2** filed a signed lease under "Finance" and a crash log under "Finance"; fixed with category-clarifying rules and two more few-shots. Final pass: 20/24 placements exactly right, 4 defensible-but-imperfect (a `.mp4` screen recording landed in Notes; grandma's jollof recipe reasoned *"recipe notes"* then chose Documents). For a 0.5B model, I'll take it — and when I want better, `--model qwen2.5:1.5b-instruct` is a one-flag upgrade; the harness doesn't change.

## Why Does Open Innovation Matter?

Not decoratively. For this specific tool, the closed option simply fails the requirements list:

**1. My Downloads folder contains a tax summary, a signed lease, and a password export.**
A cloud classifier means uploading exactly those to a server I don't control. With local inference, privacy isn't a settings toggle on a privacy policy — it's physics. Nothing leaves the machine because nothing can.

**2. It works with the internet off, forever.**
After a one-time 397 MB pull, sorting runs on a plane, in a blackout, in a village with carrier pigeons. File hygiene shouldn't have network availability as a dependency.

**3. Marginal cost is a solid, constitutional $0.00.**
A pass over 24 files is ~25k input tokens. Pennies per run on even a cheap API — but forever, nightly, on every machine in the house. Local costs nothing at any scale and burns watts you already own.

**4. The brain is swappable and tunable — no product roadmap required.**
My remaining misfires have two open fixes: bump model size with one flag, or fine-tune the small weights on *my* definition of tidy. Closed APIs deprecate models mid-project and cap customization behind enterprise tiers; Apache-2.0 weights just sit on disk being mine.

**5. Auditable behavior on sensitive files.**
The full decision loop — prompt, categories, fallback rules — is ~450 lines that fit in a head. When software is moving a file named `1password-backup-2019.txt`, "trust us" is not an architecture.

Where open beat closed during the build, concretely: I re-ran the full 24-file classification about six times while tuning the prompt — zero financial friction, no tokens-in-a-tab counting. `temperature=0` plus pinned local weights gave me bit-for-bit reproducible plans, which a silently-updated hosted model cannot. And "does it run on my potato?" stopped being a billing question and became a laptop question.

## My Agent Session

This project was built in a single AI-agent session (Arena Agent Mode): environment probes → direct-download Ollama binary → pull model → three prompt iterations, with every intermediate misclassification and the exact fixes preserved in `demo/*.log`. The session included a real failure recovery you can audit: when the model server briefly raced its own model load, the harness cleanly took the extension-rule fallback path — no crash, no wrong move; that fallback exists *because* sloths should never panic.

<!-- Save the session at devrelay.com and replace the next line: -->
<!-- {% agent_session YOUR_SESSION_ID %} -->

## The Lazy Payoff

Manual triage of a folder like this is ~15–25 minutes of pure tedium: open, skim, decide, drag, rename, second-guess. The sloth does it in ~65 seconds of *not my time* — and in watch/cron mode, it does it at 2am every night, forever, for free:

```cron
0 2 * * *  cd ~/sloth-sort && python3 sloth_sort.py apply "$HOME/Downloads" --pace 8 --siesta 2 >> "$HOME/.slothsort-nightly.log" 2>&1
```

This week it sorted the 24-file demo mess end-to-end multiple times, survived a full undo/re-apply cycle, and did its final run on hardware slower than my phone. Tonight it's going on cron for the real Downloads folder — which means the `todo list.txt` item *"sort downloads folder (lol, never)"* can finally be deleted. By me. Some work a sloth shouldn't do.

## Prize Categories

- **Best Use of Entire** — the full build session is shared in *My Agent Session* above via DevRelay.

<!-- Possible upgrades if you have time before the deadline:
- Best Use of ElevenLabs: regenerate audio/sloth-sort-audio.mp3 with ElevenLabs TTS (the script is below the Demo section/built into the audio) and note it here.
- Best Use of Render + Best Use of a .tech Domain: deploy docs/index.html (included, self-contained) as a Render static site on your free .tech domain.
- Best Use of Sentry Agent Tracing: wrap the model loop with sentry spans and add screenshots of latency/tokens per file.
Only list categories you actually wired up — judges check. -->

<!-- Thanks for participating! -->
