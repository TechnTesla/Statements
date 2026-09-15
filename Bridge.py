#!/usr/bin/env python3
"""
Statement Bridge
PDF bank statement -> LLM parse -> balance check -> Xero-ready CSV.

Setup (once):
    pip install pdfplumber anthropic
    export ANTHROPIC_API_KEY=sk-ant-...

Run:
    python statement_bridge.py mystatement.pdf

Output:
    mystatement.csv          (Xero import shape)
    Console shows any rows that FAIL the balance check.

Scope on purpose: ONE bank, TEXT pdfs only (no scans). That's v1.
"""

import sys
import os
import csv
import json
import pdfplumber
from anthropic import Anthropic

client = Anthropic()  # reads ANTHROPIC_API_KEY from env

# ---- 1. EXTRACT -----------------------------------------------------------
def extract_pages(pdf_path):
    """Return a list of page texts."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages.append(text)
    if not any(p.strip() for p in pages):
        raise SystemExit(
            "No text found — this looks like a scanned/image PDF. "
            "v1 supports text PDFs only (download the statement directly "
            "from online banking, don't scan a paper copy)."
        )
    return pages


# ---- 2. PARSE (the AI part) ----------------------------------------------
PROMPT = """You are parsing one page of an Australian bank statement.

Below is the raw text extracted from the page. Return ONLY a JSON array of
transaction objects. No prose, no markdown, no code fences. Each object:

  {{"date": "YYYY-MM-DD",
    "description": "string",
    "amount": number,          // NEGATIVE for money out, POSITIVE for money in
    "balance": number}}        // the running balance printed on that line, if present; else null

Rules:
- One object per transaction row. Ignore headers, footers, page numbers, ads.
- Keep multi-line descriptions as one description string.
- amount is a signed number (e.g. -45.20 for a debit, 1200.00 for a credit).
- If a row prints no running balance, set "balance": null.
- Do not invent rows. Do not fill gaps. Only what is on the page.

PAGE TEXT:
---
{page_text}
---
"""

def parse_page(page_text):
    if not page_text.strip():
        return []
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": PROMPT.format(page_text=page_text)}],
    )
    raw = "".join(b.text for b in msg.content if b.type == "text").strip()
    # strip accidental code fences just in case
    if raw.startswith("```"):
        raw = raw.split("```")[1].lstrip("json").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print("  ! LLM returned unparseable JSON for a page — skipping it.")
        print("    (raw head:", raw[:120], "...)")
        return []


# ---- 3. VERIFY (your code — the trust layer) ------------------------------
def balance_check(rows, tol=0.01):
    """
    For each row that has a printed balance, check
    previous_balance + amount == printed_balance.
    Returns list of (index, expected, printed) for FAILURES.
    """
    failures = []
    prev = None
    for i, r in enumerate(rows):
        bal = r.get("balance")
        amt = r.get("amount")
        if bal is None or amt is None:
            prev = bal if bal is not None else prev
            continue
        if prev is not None:
            expected = round(prev + amt, 2)
            if abs(expected - bal) > tol:
                failures.append((i, expected, bal))
        prev = bal
    return failures


# ---- 4. EXPORT ------------------------------------------------------------
def write_xero_csv(rows, out_path):
    # Xero precoded import shape: Date, Amount, Payee, Description, Reference
    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Date", "Amount", "Payee", "Description", "Reference"])
        for r in rows:
            w.writerow([r.get("date", ""),
                        r.get("amount", ""),
                        "",                       # Payee (optional)
                        r.get("description", ""),
                        ""])                      # Reference (optional)


# ---- MAIN -----------------------------------------------------------------
def main():
    if len(sys.argv) != 2:
        print("Usage: python statement_bridge.py <statement.pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    out_path = os.path.splitext(pdf_path)[0] + ".csv"

    print(f"Extracting {pdf_path} ...")
    pages = extract_pages(pdf_path)
    print(f"  {len(pages)} pages")

    all_rows = []
    for n, text in enumerate(pages, 1):
        print(f"Parsing page {n} ...")
        rows = parse_page(text)
        print(f"  {len(rows)} rows")
        all_rows.extend(rows)

    print(f"\nTotal transactions: {len(all_rows)}")

    print("Running balance check ...")
    fails = balance_check(all_rows)
    if fails:
        print(f"  ⚠ {len(fails)} row(s) FAILED the balance check — DO NOT trust blindly:")
        for i, expected, printed in fails:
            r = all_rows[i]
            print(f"    row {i}: {r.get('date')} {r.get('description')[:40]!r} "
                  f"amount={r.get('amount')} expected_balance={expected} printed={printed}")
    else:
        print("  ✓ every row with a printed balance ties out")

    write_xero_csv(all_rows, out_path)
    print(f"\nWrote {out_path}")
    if fails:
        print("Review the flagged rows before importing.")


if __name__ == "__main__":
    main()