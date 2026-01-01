#!/usr/bin/env python3
"""
Parser (fixed) — Version4 with GUI

Changes vs Version3:
 - Robust extraction for Schedule lines that include "PREMIUM DEDUCTION" and "PENSIONS" (optional).
 - Terminated records:  normalize termination month to YYYY-MM-01 for DB DATE consistency.

GUI: 
 - select a PDF / text dump,
 - choose mode (Schedule, Terminated, Statement),
 - extract and preview results,
 - export CSV.

CLI (unchanged):
 - python parser_db_ready_fixed_Version4.py --mode Statement --input statementmayraw.csv --output statement_out.csv
 - python parser_db_ready_fixed_Version4.py --mode Schedule --input schedulerawcsv.csv --output schedule_out.csv
 - python parser_db_ready_fixed_Version4.py --mode Terminated --input terminatedraw.csv --output terminated_out.csv
"""
from pathlib import Path
import argparse
import pdfplumber
import pandas as pd
import re
import unicodedata
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import sys
import os

# Optional GUI deps
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except Exception:
    tk = None

# -------------------------
# Utilities
# -------------------------
MONTHS = {
    'jan': 1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,'jul':7,'aug':8,'sep':9,'sept':9,'oct':10,'nov':11,'dec':12
}

def to_iso_date(date_str:  str) -> str:
    """Try multiple formats; return 'YYYY-MM-DD' or ''."""
    if not date_str or not isinstance(date_str, str):
        return ""
    s = date_str.strip()
    s = unicodedata.normalize("NFKC", s)
    fmts = [
        "%Y-%m-%d","%Y/%m/%d","%d/%m/%Y","%d-%b-%y","%d-%b-%Y","%d-%B-%Y",
        "%d %b %Y","%d %B %Y","%d-%m-%Y","%d/%m/%y","%m/%d/%Y","%m-%d-%Y"
    ]
    for f in fmts:
        try:
            return datetime.strptime(s, f).strftime("%Y-%m-%d")
        except Exception:
            pass
    # month-year to first of month
    m = re.search(r'([A-Za-z]{3,9})\.?\s+(\d{4})', s)
    if m:
        mon = m.group(1).lower()[:3]
        yr = int(m.group(2))
        mm = MONTHS.get(mon)
        if mm:
            return f"{yr: 04d}-{mm:02d}-01"
    # dateutil fallback
    try:
        from dateutil import parser as du_parser
        dt = du_parser.parse(s, dayfirst=True, fuzzy=True)
        return dt.strftime("%Y-%m-%d")
    except Exception: 
        return ""

def clean_decimal_2dp(v) -> str:
    """Return '' or normalized 2dp string; handles (negative) and currency symbols."""
    if v is None:
        return ""
    s = str(v).strip()
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r'[₵$£€,]', '', s)
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    # last numeric blob on the line is usually the value
    m = re.search(r'(-?\d+(?:[.,]\d+)?)(?! .*\d)', s)
    if not m:
        return ""
    try:
        d = Decimal(m.group(1).replace(",", ""))
        if neg:
            d = -d
        d = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return format(d, "f")
    except Exception:
        return ""

def month_year_to_first_iso(month_year_str: str) -> str:
    """COM_Jul_2025 or 'Jul 2025' -> '2025-07-01' (first of month anchor)."""
    if not month_year_str or not isinstance(month_year_str, str):
        return ""
    s = month_year_str.strip()
    s = re.sub(r'\s+', ' ', s)
    # Pattern 1: "Jul 2025"
    parts = s.split()
    if len(parts) == 2 and re.match(r'^\d{4}$', parts[1]):
        mon = parts[0][: 3].lower()
        mm = MONTHS.get(mon)
        if mm:
            return f"{int(parts[1]):04d}-{mm:02d}-01"
    # Pattern 2: "COM_JUL_2025"
    m = re.search(r'COM_([A-Z]{3})_(\d{4})', s, re.IGNORECASE)
    if m:
        mon = m.group(1).lower()[: 3]
        mm = MONTHS.get(mon)
        if mm:
            return f"{int(m.group(2)):04d}-{mm:02d}-01"
    return ""

# -------------------------
# Agent metadata extraction (robust)
# -------------------------
AGENT_CODE_PATTERNS = [
    r'AGENCY\s+ACCOUNT\s+NO[:\s]*([0-9A-Z\-]+)',
    r'AGENT\s+ACCOUNT\s+NO[:\s]*([0-9A-Z\-]+)',
    r'AGENT\s+ACCONT\s+NO[:\s]*([0-9A-Z\-]+)',
    r'AGENCY\s+ACCT[:\s]*([0-9A-Z\-]+)',
    r'AGENT\s+CODE[:\s]*([0-9A-Z\-]+)'
]

ADDRESS_KEYWORDS = [
    'PO BOX','P . O . BOX','P.O. BOX','P . O .Box','BOX','CANTONMENTS','P O BOX',
    'TEL:', 'TEL', 'PHONE', 'FAX', 'FAX:', 'P.O.', 'CT', 'P.O BOX', 'TOLL-FREE', 'TOLL FREE'
]

def _line_looks_like_address(ln: str) -> bool:
    if not ln:
        return False
    s = ln.upper()
    for kw in ADDRESS_KEYWORDS: 
        if kw in s: 
            return True
    if len(re.findall(r'[A-Z]', s)) < 3 and len(re.findall(r'\d', s)) >= 3:
        return True
    if 'COMPANY' in s or ('LIFE' in s and 'SIC' in s):
        return True
    return False

def find_agent_code_from_lines(lines) -> str:
    if not lines:
        return ""
    text = "\n".join(lines)
    for p in AGENT_CODE_PATTERNS:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    try:
        if len(lines) >= 7:
            target_line = lines[6]
            if not _line_looks_like_address(target_line):
                tokens = re.split(r'\s{2,}|\t|\s', target_line.strip())
                if len(tokens) >= 4:
                    candidate = re.sub(r'[^0-9A-Za-z\-]', '', tokens[3])
                    if re.match(r'^\d{3,6}$', candidate) and not re.match(r'^20\d{2}$', candidate):
                        return candidate
                tokens2 = target_line.strip().split()
                if len(tokens2) >= 4:
                    cand2 = re.sub(r'[^0-9A-Za-z\-]', '', tokens2[3])
                    if re.match(r'^\d{3,6}$', cand2) and not re.match(r'^20\d{2}$', cand2):
                        return cand2
    except Exception:
        pass
    for ln in lines[: 12]:
        if _line_looks_like_address(ln):
            continue
        m = re.search(r'\b(\d{3,6})\b', ln)
        if m:
            val = m.group(1)
            if re.match(r'^20\d{2}$', val):
                continue
            return val
    return ""

def find_agent_license_from_lines(lines) -> str:
    s = "\n".join(lines) if lines else ""
    m = re.search(r'(?:AGENT\s+LICENSE\s+NO[:\s]*|AGENCY\s+LICENSE\s+NO[:\s]*|AGENT\s+LICENSE[:\s]*)(T?\d+)', s, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m2 = re.search(r'\bT[-]?\d{3,}\b', s, re.IGNORECASE)
    if m2:
        return re.sub(r'[\s\-]', '', m2.group(0))
    return ""

def find_commission_batch_code(lines) -> str:
    s = "\n".join(lines or [])
    m = re.search(r'(COM_[A-Z]{3}_\d{4})', s, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m2 = re.search(r'Com_[A-Za-z]{3}_\d{4}', s, re.IGNORECASE)
    if m2:
        return m2.group(0).strip()
    return ""

# -------------------------
# Input (PDF or text) extraction helpers
# -------------------------
def extract_all_lines_from_pdf(pdf_path: str):
    lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                for ln in text.splitlines():
                    lines.append(ln.rstrip())
    return lines

def extract_all_lines_from_file(path: str):
    """
    Accepts: 
     - PDF paths:  uses pdfplumber
     - Plain text / CSV dumps: reads text and returns lines
    """
    p = Path(path)
    if p.suffix.lower() == ".pdf":
        return extract_all_lines_from_pdf(str(p))
    txt = p.read_text(encoding='utf-8', errors='ignore')
    lines = []
    for ln in txt.splitlines():
        ln = ln.rstrip()
        if ln.startswith('"') and ln.endswith('"'):
            ln = ln[1:-1]
        lines.append(ln)
    return lines

# -------------------------
# Parsing helpers & constants
# -------------------------
POLICY_TYPES = {"GGG", "EDU", "EPP", "FAM", "FJPP", "FLE", "FNN"}

def is_valid_policy(policy_no: str) -> bool:
    policy_no = str(policy_no).strip()
    if re.match(r'^\d{2}/\d{2}/\d{4}$', policy_no):
        return False
    if policy_no.startswith("***"):
        return False
    if not policy_no: 
        return False
    return True

def parse_names_and_policy(parts):
    policy_idx = next((i for i, p in enumerate(parts) if p in POLICY_TYPES), None)
    if policy_idx is None or policy_idx < 2:
        return "", "", "", "", 1
    name_tokens = []
    for t in parts[1:policy_idx]:
        if re.match(r"^[A-Za-z]+(?: [-'][A-Za-z]+)*$", t):
            name_tokens.append(t)
        elif t in ('-', '–', '/', '.', ''):
            continue
        else:
            break
    while len(name_tokens) < 3:
        name_tokens.append("")
    holder, surname, other_name = name_tokens[: 3]
    policy_type = parts[policy_idx]
    idx = policy_idx + 1
    return holder, surname, other_name, policy_type, idx

def correct_inception_agent(inception:  str, agent_name: str):
    agent_name = str(agent_name).strip()
    inception = str(inception).strip()
    match = re.match(r'^-? (\d{2})\s+(.*)', agent_name)
    if match:
        yy = match.group(1)
        name = match.group(2)
        if inception and not inception.endswith('-' + yy):
            inception = inception + '-' + yy
        agent_name = name
    return inception, agent_name

# -------------------------
# Date pattern to capture dd-Mon-YY and variants
# -------------------------
DATE_RE = re.compile(
    r'(\b\d{1,2}[-/][A-Za-z]{3,9}[-/]\d{2,4}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d{1,2}[-/][A-Za-z]{3,9}\b)',
    flags=re.IGNORECASE
)

# -------------------------
# Extractors
# -------------------------
def extract_statement_data(path:  str) -> pd.DataFrame:
    lines = extract_all_lines_from_file(path)
    month_year = ""
    agent_license = ""
    for ln in lines:
        m = re.search(r'COM_([A-Z]{3})_(\d{4})', ln, re.IGNORECASE)
        if m:
            month_year = f"{m.group(1)} {m.group(2)}"
            break
    agent_license = find_agent_license_from_lines(lines)
    agent_code = find_agent_code_from_lines(lines)

    extracted_rows = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.search(r'POLICY NO\.|PROPOSAL NO\.', line, re.IGNORECASE):
            is_proposal = bool(re.search(r'PROPOSAL NO\.', line, re.IGNORECASE))
            j = i + 2
            while j < len(lines):
                rowline = lines[j].strip()
                if (not rowline or rowline.upper().startswith("POLICY COUNT") or rowline.upper().startswith("PREMIUM")
                    or rowline.startswith("*** END OF FILE ***") or re.match(r'^\d{4}$', rowline)
                    or rowline.upper().startswith("TOTAL") or rowline.upper().startswith("PROPOSAL COUNT")
                    or rowline.upper().startswith("PROPOSALS") or re.search(r'NO\. HOLDER POLICY TYPE', rowline, re.IGNORECASE)):
                    break
                parts = rowline.split()
                if len(parts) < 7:
                    j += 1
                    continue
                policy_no = parts[0]
                if not is_valid_policy(policy_no):
                    j += 1
                    continue
                holder, surname, other_name, policy_type, idx = parse_names_and_policy(parts)
                row_data = parts[idx:]
                expected_fields = ["term", "pay_date", "receipt_no", "premium", "com_rate", "com_amt"]
                if is_proposal:
                    if len(row_data) > 0 and not row_data[0].isdigit():
                        row_data = ['0'] + row_data
                values = dict(zip(expected_fields, row_data + ['']*6))
                com_amt = values["com_amt"]
                inception = ""
                agent_name = ""
                trailing = row_data[6: ] if len(row_data) > 6 else []
                if trailing:
                    rest = " ".join(trailing)
                    m = DATE_RE.search(rest)
                    if m:
                        inception = to_iso_date(m.group(0))
                        agent_name = rest[m.end():].strip()
                    else:
                        agent_name = rest.strip()
                else:
                    try:
                        idx_pos = rowline.find(str(com_amt))
                        if idx_pos != -1:
                            after = rowline[idx_pos + len(str(com_amt)):]
                            m2 = DATE_RE.search(after)
                            if m2:
                                inception = to_iso_date(m2.group(0))
                                agent_name = after[m2.end():].strip()
                    except Exception:
                        pass
                    if not inception:
                        m3 = DATE_RE.search(rowline)
                        if m3:
                            inception = to_iso_date(m3.group(0))
                inception, agent_name = correct_inception_agent(inception, agent_name)
                inception = to_iso_date(inception)
                premium = clean_decimal_2dp(values["premium"])
                com_amt_norm = clean_decimal_2dp(com_amt)
                row = {
                    "agent_code": agent_code,
                    "policy_no": policy_no,
                    "holder": holder,
                    "surname": surname,
                    "other_name": other_name,
                    "policy_type": policy_type,
                    "term": values["term"],
                    "pay_date": to_iso_date(values["pay_date"]),
                    "receipt_no": values["receipt_no"],
                    "premium":  premium,
                    "com_rate": values["com_rate"],
                    "com_amt":  com_amt_norm,
                    "inception": inception,
                    "agent_name": agent_name,
                    "MONTH_YEAR": month_year,
                    "AGENT_LICENSE_NUMBER": agent_license
                }
                extracted_rows.append(row)
                j += 1
            i = j
        else: 
            i += 1
    return pd.DataFrame(extracted_rows)

def extract_terminated_data(path: str) -> pd.DataFrame:
    lines = extract_all_lines_from_file(path)
    month_year = ""
    for ln in lines:
        m = re.search(r'COM_([A-Z]{3})_(\d{4})', ln, re.IGNORECASE)
        if m:
            month_year = f"{m.group(1)} {m.group(2)}"
            break
    agent_license = find_agent_license_from_lines(lines)
    agent_code = find_agent_code_from_lines(lines)

    extracted_rows = []
    for ln in lines:
        parts = ln.split()
        if not parts:
            continue
        first_word = parts[0]
        if first_word.upper() in {"DAVID","COMIISION","CURRENCY","POLICY","TERMINATED"}:
            continue
        if not re.match(r"[A-Z]{2,6}\d{2,}", first_word):
            continue
        rn_idx = next((idx for idx, v in enumerate(parts) if v.startswith("RN") or re.match(r'^[A-Z]{2}\d+', v)), None)
        if rn_idx is None or rn_idx < 1:
            if len(parts) < 8:
                continue
            rn_idx = 2
        name_tokens = parts[1:rn_idx]
        holder = name_tokens[0] if len(name_tokens) > 0 else ""
        surname = name_tokens[1] if len(name_tokens) > 1 else ""
        other_name = " ".join(name_tokens[2:]) if len(name_tokens) > 2 else ""
        try:
            receipt_no = parts[rn_idx]
            paydate_raw = parts[rn_idx + 1] if rn_idx + 1 < len(parts) else ""
            premium_raw = parts[rn_idx + 2] if rn_idx + 2 < len(parts) else ""
            com_rate_raw = parts[rn_idx + 3] if rn_idx + 3 < len(parts) else ""
            com_amt_raw = parts[rn_idx + 4] if rn_idx + 4 < len(parts) else ""
            pt_idx = rn_idx + 5
            policy_type = parts[pt_idx] if pt_idx < len(parts) and parts[pt_idx] in POLICY_TYPES else ""
            if policy_type: 
                inc_token = parts[pt_idx + 1] if pt_idx + 1 < len(parts) else ""
                inception = to_iso_date(inc_token)
                status = parts[pt_idx + 2] if pt_idx + 2 < len(parts) else ""
                agent_name = " ".join(parts[pt_idx + 3:]) if pt_idx + 3 < len(parts) else ""
            else:
                inception = ""
                status = ""
                agent_name = ""
        except Exception:
            continue
        paydate_iso = to_iso_date(paydate_raw)
        premium = clean_decimal_2dp(premium_raw)
        com_amt = clean_decimal_2dp(com_amt_raw)
        termination_date_iso = month_year_to_first_iso(month_year)
        row = {
            "policy_no": first_word,
            "holder":  holder,
            "surname": surname,
            "other_name":  other_name,
            "receipt_no": receipt_no,
            "paydate": paydate_iso,
            "premium": premium,
            "com_rate":  com_rate_raw,
            "com_amt": com_amt,
            "policy_type": policy_type,
            "inception": inception,
            "status":  status,
            "agent_name": agent_name,
            "MONTH_YEAR": month_year,
            "AGENT_LICENSE_NUMBER": agent_license,
            "agent_code": agent_code,
            "termination_date": termination_date_iso
        }
        extracted_rows.append(row)
    return pd.DataFrame(extracted_rows)

# -------------------------
# Schedule:  improved agent_name + optional deductions
# -------------------------
COMPANY_KEYWORDS = ['COMPANY', 'LTD', 'LIMITED', 'SIC', 'LIFE', 'BANK', 'P.O.', 'PO BOX', 'CANTONMENTS', 'WWW', '@']

def extract_schedule_data(path: str) -> pd.DataFrame:
    lines = extract_all_lines_from_file(path)
    agent_name = ""
    header_idx = None
    for idx, ln in enumerate(lines[: 12]):
        if re.search(r'COMMISSION\s+SCHEDULE|COMMISSION\s+STATEMENT|COMIISION', ln, re.IGNORECASE):
            header_idx = idx
            break
    if header_idx is None:
        header_idx = 0
    for k in range(header_idx+1, min(header_idx+6, len(lines))):
        candidate = lines[k].strip()
        if not candidate:
            continue
        upper = candidate.upper()
        if any(kw in upper for kw in COMPANY_KEYWORDS) or _line_looks_like_address(candidate):
            continue
        if len(candidate.split()) < 2:
            continue
        agent_name = candidate
        break
    if not agent_name:
        for ln in lines[:12]:
            ln_strip = ln.strip()
            if not ln_strip:
                continue
            if _line_looks_like_address(ln_strip):
                continue
            if re.search(r'^[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,6}$', ln_strip):
                agent_name = ln_strip
                break

    commission_batch_code = find_commission_batch_code(lines)
    agent_license = find_agent_license_from_lines(lines)
    agent_code = find_agent_code_from_lines(lines)

    total_premiums = None
    income = None
    gov_tax = None
    siclase = None
    welfareko = None
    premium_deduction = None
    pensions = None
    total_deductions = None
    net_commission = None
    document_date = None

    for ln in lines:
        # TOTAL PREMIUM - match the specific pattern on same line
        if re.search(r'TOTAL\s+PREMIUM\s+', ln, re.IGNORECASE):
            match = re.search(r'TOTAL\s+PREMIUM\s+([0-9,]+\.?\d{0,2})', ln, re.IGNORECASE)
            if match:
                total_premiums = clean_decimal_2dp(match.group(1))

        # GROSS COMMISSION / INCOME
        if re.search(r'GROSS\s+COMMISSION\s+EARNED|INCOME\b', ln, re.IGNORECASE):
            m = re.search(r'([0-9,]+\.\d{2})', ln)
            if m:
                income = clean_decimal_2dp(m.group(1))

        # GOV TAX
        if re.search(r'GOV\.\s*TAX', ln, re.IGNORECASE):
            m = re.search(r'([0-9,]+\.\d{2})', ln)
            if m:
                gov_tax = clean_decimal_2dp(m.group(1))

        # SICLASE
        if re.search(r'\bSICLASE\b', ln, re.IGNORECASE):
            m = re.search(r'([0-9,]+\.?\d{0,2})', ln)
            if m:
                siclase = clean_decimal_2dp(m.group(1))

        # WELFAREKO
        if re.search(r'\bWELFAREKO\b', ln, re.IGNORECASE):
            m = re.search(r'([0-9,]+\.?\d{0,2})', ln)
            if m:
                welfareko = clean_decimal_2dp(m.group(1))

        # PREMIUM DEDUCTION
        if re.search(r'\bPREMIUM\s+DEDUCTION\b', ln, re.IGNORECASE):
            m = re.search(r'([0-9,]+\.?\d{0,2})', ln)
            if m:
                premium_deduction = clean_decimal_2dp(m.group(1))

        # PENSIONS
        if re.search(r'\bPENSIONS\b', ln, re.IGNORECASE):
            m = re.search(r'([0-9,]+\.\d{2})', ln)
            if m:
                pensions = clean_decimal_2dp(m.group(1))

        # TOTAL DEDUCTIONS - match pattern with parentheses:  "(2,548.27)"
        if re.search(r'TOTAL\s+DEDUCTIONS', ln, re.IGNORECASE):
            m = re.search(r'\(([0-9,]+\.\d{2})\)', ln)
            if m:
                total_deductions = clean_decimal_2dp(m.group(1))

        # NET COMMISSION
        if re.search(r'NET\s+COMMISSION', ln, re.IGNORECASE):
            m = re.search(r'([0-9,]+\.\d{2})', ln)
            if m:
                net_commission = clean_decimal_2dp(m.group(1))

        # A date somewhere in the footer/header
        m = re.search(r'(\d{2}/\d{2}/\d{4})', ln)
        if m and not document_date:
            document_date = to_iso_date(m.group(1))

    row = {
        "agent_code": agent_code,
        "agent_name": agent_name,
        "AGENT_LICENSE_NUMBER": agent_license,
        "commission_batch_code": commission_batch_code,
        "total_premiums": total_premiums,
        "income": income,
        "gov_tax": gov_tax,
        "siclase": siclase,
        "welfareko": welfareko,
        "premium_deduction":  premium_deduction,
        "pensions": pensions,
        "total_deductions": total_deductions,
        "net_commission": net_commission,
        "document_date": document_date,
        "MONTH_YEAR": ""
    }
    if commission_batch_code:
        m = re.search(r'COM_([A-Z]{3})_(\d{4})', commission_batch_code, re.IGNORECASE)
        if m:
            row['MONTH_YEAR'] = f"{m.group(1)} {m.group(2)}"
    return pd.DataFrame([row])

# -------------------------
# CLI wiring
# -------------------------
def run_cli_mode(args):
    p = Path(args.input)
    if not p.exists():
        print("Input not found:", p, file=sys.stderr)
        sys.exit(2)
    mode = args.mode
    if mode == "Statement":
        df = extract_statement_data(str(p))
        out_cols = ["agent_code","policy_no","holder","surname","other_name","policy_type","term","pay_date",
                    "receipt_no","premium","com_rate","com_amt","inception","agent_name",
                    "MONTH_YEAR","AGENT_LICENSE_NUMBER"]
        for c in out_cols:
            if c not in df.columns:
                df[c] = ""
        df = df[out_cols]
        df.to_csv(args.output, index=False)
        print(f"Wrote statement DB-ready CSV:  {args.output} rows={len(df)}")
    elif mode == "Terminated":
        df = extract_terminated_data(str(p))
        out_cols = ["agent_code","policy_no","holder","surname","other_name","receipt_no","paydate","premium",
                    "com_rate","com_amt","policy_type","inception","termination_date","status","agent_name",
                    "MONTH_YEAR","AGENT_LICENSE_NUMBER"]
        for c in out_cols: 
            if c not in df.columns:
                df[c] = ""
        df = df[out_cols]
        df.to_csv(args.output, index=False)
        print(f"Wrote terminated DB-ready CSV: {args.output} rows={len(df)}")
    elif mode == "Schedule":
        df = extract_schedule_data(str(p))
        out_cols = ["agent_code","agent_name","AGENT_LICENSE_NUMBER","commission_batch_code","total_premiums",
                    "income","gov_tax","siclase","welfareko","premium_deduction","pensions",
                    "total_deductions","net_commission","document_date","MONTH_YEAR"]
        for c in out_cols: 
            if c not in df.columns:
                df[c] = ""
        df = df[out_cols]
        df.to_csv(args.output, index=False)
        print(f"Wrote schedule DB-ready CSV: {args.output} rows={len(df)}")
    else:
        print("Unknown mode", mode)
        sys.exit(3)

# -------------------------
# Minimal GUI (Tkinter)
# -------------------------
class CombinedExtractorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Schedule, Terminated & Statement PDF Extractor (Version4)")
        self.root.geometry("1200x800")
        self.selected_file = None
        self.df = pd.DataFrame()
        self.mode = tk.StringVar(value="Schedule")

        ttk.Label(root, text="Select PDF/Text Type:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        pdf_types = ["Schedule","Terminated","Statement"]
        self.type_menu = ttk.Combobox(root, textvariable=self.mode, values=pdf_types, state="readonly")
        self.type_menu.grid(row=0, column=1, padx=5, pady=5)
        self.type_menu.current(0)

        self.file_label = ttk.Label(root, text="No file selected")
        self.file_label.grid(row=1, column=0, columnspan=2, sticky='w', padx=5)
        ttk.Button(root, text="Select File", command=self.select_file).grid(row=1, column=2, padx=5)
        ttk.Button(root, text="Extract", command=self.extract_pdf).grid(row=1, column=3, padx=5)
        ttk.Button(root, text="Export CSV", command=self.export_csv).grid(row=1, column=4, padx=5)
        ttk.Button(root, text="Save Preview as CSV", command=self.save_preview_csv).grid(row=1, column=5, padx=5)

        self.table_frame = tk.Frame(root)
        self.table_frame.grid(row=2, column=0, columnspan=6, sticky='nsew')
        root.grid_rowconfigure(2, weight=1)
        root.grid_columnconfigure(5, weight=1)

    def select_file(self):
        filetypes = [("PDF files","*.pdf"),("Text/CSV","*.csv;*.txt"),("All files","*.*")]
        fp = filedialog.askopenfilename(filetypes=filetypes)
        if fp:
            self.selected_file = fp
            self.file_label.config(text=os.path.basename(fp))

    def extract_pdf(self):
        if not self.selected_file:
            messagebox.showwarning("No file","Select a file first")
            return
        m = self.mode.get()
        try:
            if m == "Schedule":
                self.df = extract_schedule_data(self.selected_file)
            elif m == "Terminated": 
                self.df = extract_terminated_data(self.selected_file)
            elif m == "Statement":
                self.df = extract_statement_data(self.selected_file)
            else:
                self.df = pd.DataFrame()
        except Exception as e:
            messagebox.showerror("Error", f"Error during extraction:\n{e}")
            self.df = pd.DataFrame()
            return
        self.preview()

    def preview(self):
        for w in self.table_frame.winfo_children():
            w.destroy()
        if self.df is None or self.df.empty:
            ttk.Label(self.table_frame, text="No data").pack()
            return
        cols = list(self.df.columns)
        tree = ttk.Treeview(self.table_frame, columns=cols, show='headings')
        vsb = ttk.Scrollbar(self.table_frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(self.table_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side='right', fill='y')
        hsb.pack(side='bottom', fill='x')
        tree.pack(fill='both', expand=True)
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=120, anchor='w')
        for _, r in self.df.iterrows():
            vals = [r.get(c, "") for c in cols]
            tree.insert('', 'end', values=vals)

    def export_csv(self):
        if self.df is None or self.df.empty:
            messagebox.showinfo("No data", "No extracted data to export")
            return
        fp = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV","*.csv")])
        if fp:
            try:
                self.df.to_csv(fp, index=False)
                messagebox.showinfo("Saved", f"Saved to {fp}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save CSV:\n{e}")

    def save_preview_csv(self):
        if self.df is None or self.df.empty:
            messagebox.showinfo("No data", "No extracted data to save")
            return
        base = "extracted_preview.csv"
        if self.selected_file:
            base = Path(self.selected_file).with_suffix('').name + "_extracted.csv"
        fp = filedialog.asksaveasfilename(initialfile=base, defaultextension=".csv", filetypes=[("CSV","*.csv")])
        if fp:
            try: 
                self.df.to_csv(fp, index=False)
                messagebox.showinfo("Saved", f"Saved to {fp}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save CSV:\n{e}")

# -------------------------
# Main / CLI entry
# -------------------------
def main():
    if len(sys.argv) == 1:
        if tk is None:
            print("Tkinter not available. Use CLI arguments.", file=sys.stderr)
            return
        root = tk.Tk()
        app = CombinedExtractorGUI(root)
        root.mainloop()
        return
    ap = argparse.ArgumentParser(description="DB-ready parser (fixed) - Version4")
    ap.add_argument("--mode", choices=["Schedule","Terminated","Statement"], required=True)
    ap.add_argument("--input", "-i", required=True)
    ap.add_argument("--output", "-o", required=True)
    args = ap.parse_args()
    run_cli_mode(args)

if __name__ == "__main__":
    main()