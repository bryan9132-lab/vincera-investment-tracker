"""
PDF Parsers — one function per broker format.
Each returns a standardised ParsedPDF dataclass.
"""

import re
import io
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import fitz          # pymupdf
from PIL import Image
import pytesseract


# ── Output structure ────────────────────────────────────────────────────────

@dataclass
class ParsedTrade:
    security_code:  str
    shares:         float   # negative = sell
    price:          float
    gross_amount:   float
    fee:            float
    tax:            float
    net_amount:     float
    memo:           Optional[str] = None

@dataclass
class ParsedPDF:
    account_no:     str
    trade_date:     date
    settle_date:    Optional[date]
    broker:         str
    trades:         list = field(default_factory=list)
    raw_text:       str = ''
    errors:         list = field(default_factory=list)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _roc_to_date(roc_str: str) -> Optional[date]:
    """Convert ROC date string like '115/01/16' to Python date (2026-01-16)"""
    try:
        parts = roc_str.strip().split('/')
        year  = int(parts[0]) + 1911
        month = int(parts[1])
        day   = int(parts[2])
        return date(year, month, day)
    except Exception:
        return None

def _clean_number(s: str) -> float:
    """'1,234.56' → 1234.56"""
    return float(s.replace(',', '').strip())

def _pdf_to_text(pdf_bytes: bytes) -> str:
    """Standard text extraction (works for 統一 and 國泰)"""
    doc  = fitz.open(stream=pdf_bytes, filetype='pdf')
    text = '\n'.join(page.get_text() for page in doc)
    doc.close()
    return text

def _pdf_to_ocr_text(pdf_bytes: bytes, dpi: int = 300) -> str:
    """OCR extraction for 元大 (MingLiU font encoding issue)"""
    doc    = fitz.open(stream=pdf_bytes, filetype='pdf')
    texts  = []
    for page in doc:
        mat  = fitz.Matrix(dpi / 72, dpi / 72)
        pix  = page.get_pixmap(matrix=mat)
        img  = Image.open(io.BytesIO(pix.tobytes('png')))
        text = pytesseract.image_to_string(img, lang='chi_tra+eng')
        texts.append(text)
    doc.close()
    return '\n'.join(texts)

def detect_broker(pdf_bytes: bytes) -> str:
    """
    Detect broker from PDF text.
    Returns '統一', '元大', or '國泰'
    """
    text = _pdf_to_text(pdf_bytes)
    if '統一綜合證券' in text:
        return '統一'
    if '國泰綜合證券' in text:
        return '國泰'
    # 元大 has encoding issues — check for CorpTradeDetailFill which survives
    if 'CorpTradeDetailFill' in text:
        return '元大'
    return 'unknown'


# ── 統一 Parser ──────────────────────────────────────────────────────────────

def parse_tuni(pdf_bytes: bytes) -> ParsedPDF:
    """
    Parse 統一綜合證券 transaction PDF.
    Account number is in header: 客戶帳號 e.g. 600885-3
    """
    text   = _pdf_to_text(pdf_bytes)
    result = ParsedPDF(account_no='', trade_date=None,
                       settle_date=None, broker='統一', raw_text=text)

    # Account number
    acc_match = re.search(r'(\d{6})-\d', text)
    if acc_match:
        result.account_no = acc_match.group(1)
    else:
        result.errors.append('Could not find account number')
        return result

    # Trade date — search across whitespace/newlines (PDF has large gaps between label and value)
    # Try 8-digit format first: 20260505
    date_match = re.search(r'交易日期.*?(\d{8})', text, re.DOTALL)
    if date_match:
        d = date_match.group(1)
        result.trade_date = date(int(d[:4]), int(d[4:6]), int(d[6:8]))
    else:
        # Try 2-digit year format: 26/05/05
        date_match2 = re.search(r'交易日期.*?(\d{2})/(\d{2})/(\d{2})', text, re.DOTALL)
        if date_match2:
            y, m, d_str = date_match2.groups()
            result.trade_date = date(2000 + int(y), int(m), int(d_str))
        else:
            result.errors.append('Could not find trade date')
            return result

    # Parse trade rows — supports two 統一 formats:
    # Format A (VIP report): 買進|賣出 with account/name prefix
    #   600826-4 陳仕信 買進 7769 鴻勁 7200.00 .500 3,600,000 1,314 0 ...
    # Format B (standard): 買入|賣出 action-first
    #   買入 6949 沛爾生醫 359.50 1.000 359,500 224 0 ...

    # Format A pattern (個人當日交易明細表 — action=買進/賣出, shares may start with .)
    pattern_a = re.compile(
        r'\d{6}-\d\s+'            # account number e.g. 600826-4
        r'[\w\s]+?'               # customer name (non-greedy)
        r'(買進|賣出)\s+'           # action
        r'(\w+)\s+'               # stock code
        r'([\w\-\.]+(?:\s[\w\-\.]+)?)\s+'  # stock name
        r'([\d,\.]+)\s+'          # price
        r'(\.?[\d,\.]+)\s+'      # shares (may start with . e.g. .500)
        r'([\d,]+)\s+'            # gross amount
        r'([\d,]+)\s+'            # fee
        r'([\d,]+)'               # tax
    )

    # Format B pattern (standard format — action=買入/賣出)
    pattern_b = re.compile(
        r'(賣出|買入)\s+'
        r'(\w+)\s+'
        r'([\w\-\.]+(?:\s[\w\-\.]+)?)\s+'
        r'([\d,\.]+)\s+'
        r'(\.?[\d,\.]+)\s+'
        r'([\d,]+)\s+'
        r'([\d,]+)\s+'
        r'([\d,]+)'
    )

    def _parse_matches(matches, action_group, code_group, price_group,
                       zhang_group, gross_group, fee_group, tax_group, sell_keywords):
        trades = []
        for m in matches:
            action       = m.group(action_group)
            code         = m.group(code_group)
            price        = _clean_number(m.group(price_group))
            shares_zhang = _clean_number(m.group(zhang_group))
            shares       = round(shares_zhang * 1000)
            gross        = _clean_number(m.group(gross_group))
            fee          = _clean_number(m.group(fee_group))
            tax          = _clean_number(m.group(tax_group))
            line_end     = text.find('\n', m.end())
            line         = text[m.start():line_end if line_end > 0 else m.end() + 80]
            net_nums     = re.findall(r'[\d,]+', line[m.end() - m.start():])
            net          = _clean_number(net_nums[-1]) if net_nums else gross - fee - tax
            if action in sell_keywords:
                shares = -shares
            trades.append(ParsedTrade(
                security_code=code, shares=shares, price=price,
                gross_amount=gross, fee=fee, tax=tax, net_amount=net,
            ))
        return trades

    # Try Format A first
    matches_a = list(pattern_a.finditer(text))
    if matches_a:
        result.trades = _parse_matches(
            matches_a,
            action_group=1, code_group=2, price_group=4,
            zhang_group=5, gross_group=6, fee_group=7, tax_group=8,
            sell_keywords={'賣出'}
        )
    else:
        # Try Format B
        matches_b = list(pattern_b.finditer(text))
        result.trades = _parse_matches(
            matches_b,
            action_group=1, code_group=2, price_group=4,
            zhang_group=5, gross_group=6, fee_group=7, tax_group=8,
            sell_keywords={'賣出'}
        )

    if not result.trades:
        result.errors.append('No trades found — check PDF format')

    return result


# ── 國泰 Parser ──────────────────────────────────────────────────────────────

def parse_cathay(pdf_bytes: bytes) -> ParsedPDF:
    """
    Parse 國泰綜合證券 transaction PDF.
    Account number in header: 客戶 :8880-007065-0
    """
    text   = _pdf_to_text(pdf_bytes)
    result = ParsedPDF(account_no='', trade_date=None,
                       settle_date=None, broker='國泰', raw_text=text)

    # Account number — 6-digit after second dash: 8880-007065-0
    acc_match = re.search(r'8880-(\d{6})-', text)
    if acc_match:
        result.account_no = acc_match.group(1)
    else:
        result.errors.append('Could not find account number')
        return result

    # Trade date — format: 115/05/05
    date_match = re.search(r'(\d{3}/\d{2}/\d{2})\s+(?:集買|集賣|OT買|OT賣)', text)
    if date_match:
        result.trade_date = _roc_to_date(date_match.group(1))
    else:
        # Fallback: first ROC date in document
        date_match = re.search(r'(\d{3}/\d{2}/\d{2})', text)
        if date_match:
            result.trade_date = _roc_to_date(date_match.group(1))
        else:
            result.errors.append('Could not find trade date')
            return result

    # Settle date — appears after trade date on same lines
    settle_match = re.search(r'(\d{3}/\d{2}/\d{2})\s*$', text, re.MULTILINE)
    if settle_match:
        result.settle_date = _roc_to_date(settle_match.group(1))

    # Trade rows pattern — handles FANG+ names and variable optional fields
    trade_pattern = re.compile(
        r'\d{3}/\d{2}/\d{2}\s+'
        r'(集買|集賣|OT買|OT賣)\s+'
        r'(\w+)\s+'               # stock code
        r'([\w\-\+\s]+?)\s+'     # stock name (allow + for FANG+)
        r'([\d,]+)\s+'            # shares
        r'([\d,\.]+)\s+'          # price
        r'([\d,]+)\s+'            # gross
        r'([\d,]+)'               # fee
        r'(?:[\s\d,]+?)'          # skip optional fields (非貪婪)
        r'([\d,]{5,})\([收付]\)'  # net amount (min 5 chars)
    )

    for m in trade_pattern.finditer(text):
        action = m.group(1)
        code   = m.group(2).strip()
        shares = _clean_number(m.group(4))
        price  = _clean_number(m.group(5))
        gross  = _clean_number(m.group(6))
        fee    = _clean_number(m.group(7))
        tax    = 0.0  # extracted separately below if needed
        net    = _clean_number(m.group(8))

        if action in ('集賣', 'OT賣'):
            shares = -shares

        result.trades.append(ParsedTrade(
            security_code = code.strip(),
            shares        = shares,
            price         = price,
            gross_amount  = gross,
            fee           = fee,
            tax           = tax,
            net_amount    = net,
        ))

    if not result.trades:
        result.errors.append('No trades found — check PDF format')

    return result


# ── 元大 Parser (OCR) ────────────────────────────────────────────────────────

def parse_yuanta(pdf_bytes: bytes) -> ParsedPDF:
    """
    Parse 元大證券 transaction PDF via OCR.
    Uses OCR because MingLiU font has encoding issues.
    """
    text   = _pdf_to_ocr_text(pdf_bytes)
    result = ParsedPDF(account_no='', trade_date=None,
                       settle_date=None, broker='元大', raw_text=text)

    # Account number — survives OCR well: 133376-7 or 133311-0
    acc_match = re.search(r'(13\d{4})-\d', text)
    if acc_match:
        result.account_no = acc_match.group(1)
    else:
        result.errors.append('Could not find account number')
        return result

    # Trade date — OCR reads 115/01/16 reliably
    date_match = re.search(r'(\d{3}/\d{2}/\d{2})', text)
    if date_match:
        result.trade_date = _roc_to_date(date_match.group(1))
    else:
        result.errors.append('Could not find trade date')
        return result

    # Settle date — second date in doc
    all_dates = re.findall(r'(\d{3}/\d{2}/\d{2})', text)
    if len(all_dates) >= 2:
        result.settle_date = _roc_to_date(all_dates[1])

    # Trade rows — OCR preserves numbers well
    # Pattern: 4-digit stock code, then buy/sell shares columns, price, amounts
    # Example OCR line: "6949 jie Re-A 8 359.50 1,000, 359,500, 224 59,724"
    # We look for lines with a 4-digit code followed by numbers
    trade_pattern = re.compile(
        r'(\d{4,6})\s+'           # stock code
        r'[\w\s\-\.]+?'           # garbled stock name (ignored)
        r'([\d,\.]+)\s+'          # price
        r'([\d,]+)[,\s]+'         # buy shares (0 if sell)
        r'(?:([\d,]+)[,\s]+)?'    # sell shares (optional)
        r'([\d,]+)[,\s]+'         # gross amount
        r'([\d,]+)'               # fee
    )

    for m in trade_pattern.finditer(text):
        code        = m.group(1)
        price       = _clean_number(m.group(2))
        buy_shares  = _clean_number(m.group(3))
        sell_shares = _clean_number(m.group(4)) if m.group(4) else 0
        gross       = _clean_number(m.group(5))
        fee         = _clean_number(m.group(6))

        # Determine direction
        if sell_shares > 0 and buy_shares == 0:
            shares = -sell_shares
        elif buy_shares > 0:
            shares = buy_shares
        else:
            # Can't determine — skip
            continue

        # Net: gross - fee - tax (tax ~ 0.3% of gross for sells)
        tax = round(gross * 0.003, 0) if shares < 0 else 0
        net = gross - fee - tax

        result.trades.append(ParsedTrade(
            security_code = code,
            shares        = shares,
            price         = price,
            gross_amount  = gross,
            fee           = fee,
            tax           = tax,
            net_amount    = net,
        ))

    # De-duplicate (OCR sometimes picks up summary rows)
    seen  = set()
    deduped = []
    for t in result.trades:
        key = (t.security_code, t.shares, t.price)
        if key not in seen:
            seen.add(key)
            deduped.append(t)
    result.trades = deduped

    if not result.trades:
        result.errors.append('No trades found — OCR may need review')

    return result


# ── Main entry point ─────────────────────────────────────────────────────────

def parse_pdf(pdf_bytes: bytes, filename: str = '') -> ParsedPDF:
    """Auto-detect broker and parse PDF"""
    broker = detect_broker(pdf_bytes)
    if broker == '統一':
        return parse_tuni(pdf_bytes)
    elif broker == '國泰':
        return parse_cathay(pdf_bytes)
    elif broker == '元大':
        return parse_yuanta(pdf_bytes)
    else:
        result = ParsedPDF(account_no='', trade_date=None,
                           settle_date=None, broker='unknown')
        result.errors.append(f'Unknown broker format in {filename}')
        return result
