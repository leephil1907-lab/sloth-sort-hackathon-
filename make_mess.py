#!/usr/bin/env python3
"""make_mess.py — generate a painfully realistic messy Downloads folder.

Real PDFs (reportlab), a real .docx, camera imports with no readable content,
temp junk — the stuff Sloth Sort was born to eat.
"""
import json
import os
import random
import struct
import sys
import zlib
import zipfile
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "demo/messy_downloads").resolve()
random.seed(7)


def tiny_png(w: int = 96, h: int = 64) -> bytes:
    """Minimal valid-ish PNG written with stdlib only (content is irrelevant —
    photos are classified by filename)."""
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + bytes(random.randint(0, 255) for _ in range(3 * w))
                   for _ in range(h))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def make_pdf(path: Path, lines: list[str]) -> None:
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setFont("Helvetica", 11)
    y = 720
    for ln in lines:
        c.drawString(72, y, ln)
        y -= 18
    c.save()


def make_docx(path: Path, paras: list[str]) -> None:
    body = "".join(
        f"<w:p><w:r><w:t xml:space='preserve'>{t}</w:t></w:r></w:p>" for t in paras)
    doc = ("<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
           "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>"
           f"<w:body>{body}</w:body></w:document>")
    ct = ("<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
          "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'>"
          "<Default Extension='rels' ContentType='application/vnd.openxmlformats-package.relationships+xml'/>"
          "<Default Extension='xml' ContentType='application/xml'/>"
          "<Override PartName='/word/document.xml' ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'/>"
          "</Types>")
    rels_root = ("<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
                 "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>"
                 "<Relationship Id='rId1' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument' Target='word/document.xml'/>"
                 "</Relationships>")
    rels = ("<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
            "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'/>")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels_root)
        z.writestr("word/document.xml", doc)
        z.writestr("word/_rels/document.xml.rels", rels)


def W(rel: str, data) -> None:
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        p.write_text(data)
    else:
        p.write_bytes(data)


def main() -> None:
    if ROOT.exists():
        import shutil
        shutil.rmtree(ROOT)
    ROOT.mkdir(parents=True)

    # --- camera imports & media (no readable content, classified by name) ---
    W("IMG_8102.PNG", tiny_png())
    W("IMG_8144.PNG", tiny_png(128, 96))
    W("PXL_20250914_181204.jpg", os.urandom(48 * 1024))
    W("Screenshot 2025-10-02 at 18.41.22.png", tiny_png(200, 120))
    W("Screen Recording 2025-09-28.mp4", os.urandom(64 * 1024))
    W("cat_meme_FINAL.jpg", os.urandom(36 * 1024))

    # --- money & official paper (real PDFs, real text) ---
    make_pdf(ROOT / "receipt_oct_ark_cafe.pdf", [
        "ARK CAFE", "10/12/2025  08:14", "",
        "Flat White x2        7.00", "Banana bread          3.50",
        "Service charge        0.70", "TOTAL                11.20",
        "", "Card **** 4417      PAID", "THANK YOU - COME AGAIN"])
    make_pdf(ROOT / "invoice_INV-2204_final_FINAL (2).pdf", [
        "INVOICE  INV-2204", "From: Ferrous Data Ltd", "Bill to: A. Nnamdi", "",
        "Cloud storage Q3 (3 months)       45.00", "Domain renewal (1 yr)           14.99",
        "Support plan                       0.00", "", "Balance due: 59.99",
        "Due date: 2025-10-30"])
    make_pdf(ROOT / "tax_summary_2024.pdf", [
        "PERSONAL INCOME TAX SUMMARY - TY2024", "Confidential - keep on file", "",
        "Gross employment income:      18,240,000", "Pension contributions:         1,459,200",
        "Withholding tax paid:          1,104,000", "Reliefs claimed:                 200,000",
        "", "Prepared by self, review with accountant."])
    make_pdf(ROOT / "rental_agreement_signed.pdf", [
        "RESIDENTIAL TENANCY AGREEMENT", "Property: Flat 4B, 12 Adewale Close, Lekki Phase 1",
        "Tenant: A. Nnamdi   Landlord: C. Bello", "",
        "Term: 12 months from 2025-08-01", "Monthly rent: 2,400,000 NGN p.a., monthly equiv 200,000",
        "Deposit: 400,000 NGN (refundable)", "", "Signed by both parties, 2025-07-28"])
    W("bank_statement_sept.csv", "\n".join([
        "date,description,amount,balance",
        "2025-09-01,SALARY ACME TECH,1520000.00,1902100.00",
        "2025-09-05,ARK CAFE,-1120.00,1900980.00",
        "2025-09-12,TRANSFER RENT C.BELLO,-200000.00,1700980.00",
        "2025-09-20,FERROUS DATA LTD,-14999.00,1685981.00"]))

    # --- personal notes ---
    W("meeting notes monday.txt",
      "standup notes - Mon Oct 13\n- Priya: payments API in review\n- me: block the release until retry bug #482 is closed\n- action: write the alt-flow playtest plan before Friday\n- note to self: book dentist\n")
    W("jollof recipe grandma.md",
      "# Grandma's Party Jollof\n\n- 4 cups long grain parboiled rice\n- 6 red bell peppers + 2 scotch bonnets + onion, blended\n- 2 tins plum tomatoes, fried down in 1/2 cup oil\n- stock, bay, thyme, curry, salt\n\nFry base till the oil splits. Add rice, steam low 30 min. Smoke if brave.\n")
    W("todo list.txt",
      "- renew passport\n- pay DSTV\n- fix bike brake\n- CALL MUM BACK\n- sort downloads folder (lol, never)\n")
    W("lecture w4 notes.txt",
      "ECON 201 - week 4 - elasticity\nep < 1 -> inelastic (fuel, insulin)\nrevenue increases when price rises for inelastic goods\nexam tip: cross-price elasticity sign = substitutes vs complements\n")
    W("Untitled document (7).txt", "the quick brown fox\n")

    # --- a real office letter ---
    make_docx(ROOT / "letter to landlord.docx", [
        "Dear Mr Bello,",
        "Following our tenancy agreement of Flat 4B, 12 Adewale Close, this letter confirms my notice to carry out the agreed repainting before my renewal on 01 August.",
        "Kindly confirm the paint colour approved for the sitting room.",
        "Regards,", "A. Nnamdi", "12 October 2025"])

    # --- sensitive stuff (the reason this must stay local!) ---
    W("1password-backup-2019.txt",
      "LEGACY password export - migrated to new vault 2023, kept for archive\n"
      "site,login,password(old)\n"
      "oldforums.example,ada_nn,hunter22\nbank-app-2019,ada_nn,R3dacted_old_pin\n")
    W("api_keys_OLD_ROTATED.json", json.dumps({
        "_note": "ALL KEYS ROTATED 2024-03. kept for audit only.",
        "gerbil-dynamo-prod": "gdn_live_TOTALLY_FAKE_3ab1c9",
        "gerbil-dynamo-stage": "gdn_test_TOTALLY_FAKE_77f0dd",
        "cloudyrainy": "cr_TOTALLY_FAKE_91ae01"}))

    # --- code ---
    W("data_pipeline.py",
      "import csv, sys\n"
      "def clean(row):\n    return [c.strip().lower() for c in row]\n"
      "rows = (clean(r) for r in csv.reader(sys.stdin))\n"
      "out(rows)\n")

    # --- installers / junk ---
    W("gerbil-dynamo-plugin.dmg", os.urandom(40 * 1024))
    W("tmp9F31.tmp", "ses=7c41f7; cache_bust=1\n")
    W("tsdump_error_20251009.log", '2025-10-09 22:41:57 uid=webstat.2.2-1732155475.217-5 lg_prefix=tsdump cmdline=docquery {"file_uid":"webstat","format":"tsv"}\n' * 3)
    W(".DS_Store", os.urandom(2048))

    files = [p for p in sorted(ROOT.rglob("*")) if p.is_file()]
    print(f"🌴 Made a mess: {len(files)} files in {ROOT}")
    for p in files:
        print(f"   {p.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
