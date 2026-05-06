"""
Generate 庫存總表 Excel report for Richard
Clean, simple — no complex formulas needed since we compute everything in Python
"""

import tempfile
import os
from datetime import date
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from .models import db, Position, Security, ENTITIES


def generate_excel() -> str:
    """
    Generate 庫存總表 Excel and return filepath.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = '庫存總表(台灣)'

    # ── Styles ───────────────────────────────────────────────────────────────
    header_font    = Font(name='微軟正黑體', bold=True, size=10, color='FFFFFF')
    header_fill    = PatternFill('solid', start_color='1F4E79')
    subheader_fill = PatternFill('solid', start_color='2E75B6')
    alt_fill       = PatternFill('solid', start_color='D6E4F0')
    total_fill     = PatternFill('solid', start_color='BDD7EE')
    bold_font      = Font(name='微軟正黑體', bold=True, size=10)
    normal_font    = Font(name='微軟正黑體', size=10)
    center         = Alignment(horizontal='center', vertical='center')
    right          = Alignment(horizontal='right', vertical='center')
    thin           = Side(style='thin', color='B8CCE4')
    border         = Border(left=thin, right=thin, top=thin, bottom=thin)

    num_fmt        = '#,##0'
    price_fmt      = '#,##0.00'
    pnl_fmt        = '+#,##0;-#,##0;0'

    today_str      = date.today().strftime('%Y/%m/%d')

    # ── Title ────────────────────────────────────────────────────────────────
    ws.merge_cells('A1:N1')
    ws['A1'] = f'庫存總表（台灣）　　　　單位：NTD　　　日期：{today_str}'
    ws['A1'].font      = Font(name='微軟正黑體', bold=True, size=13)
    ws['A1'].alignment = center
    ws.row_dimensions[1].height = 28

    # ── Column headers ───────────────────────────────────────────────────────
    # Columns: 股票代號 | 股票名稱 | 市價 | RC張數 | RC每股成本 | RC金額 | 華強張數 | 華強每股成本 | 華強金額 | 私銀RC張數 | 私銀RC成本 | 私銀RC金額 | 私銀華強張數 | 私銀華強成本 | 私銀華強金額 | 未實現損益RC | 未實現損益華強 | 未實現損益私RC | 未實現損益私強
    headers = [
        '股票代號', '股票名稱', '市價',
        'RC\n張數', 'RC\n每股成本', 'RC\n金額',
        '華強\n張數', '華強\n每股成本', '華強\n金額',
        '私銀RC\n張數', '私銀RC\n每股成本', '私銀RC\n金額',
        '私銀華強\n張數', '私銀華強\n每股成本', '私銀華強\n金額',
        '未實現\nRC', '未實現\n華強', '未實現\n私RC', '未實現\n私強',
    ]

    col_widths = [10, 18, 10, 8, 12, 12, 8, 12, 12, 8, 12, 12, 8, 12, 12, 12, 12, 12, 12]

    for i, (h, w) in enumerate(zip(headers, col_widths), 1):
        cell              = ws.cell(2, i, h)
        cell.font         = header_font
        cell.fill         = header_fill
        cell.alignment    = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border       = border
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[2].height = 32

    # ── Fetch all active positions ───────────────────────────────────────────
    positions = Position.query.filter(Position.shares > 0).all()

    # Group by security_code
    by_code = {}
    for pos in positions:
        code = pos.security_code
        if code not in by_code:
            sec = Security.query.get(code)
            by_code[code] = {
                'name':       sec.name if sec else code,
                'last_price': pos.last_price,
                'entities':   {}
            }
        by_code[code]['last_price'] = pos.last_price  # same for all entities
        by_code[code]['entities'][pos.entity] = pos

    # ── Data rows ────────────────────────────────────────────────────────────
    row = 3
    for code, data in sorted(by_code.items()):
        price = data['last_price']
        ents  = data['entities']

        def get(entity, attr):
            pos = ents.get(entity)
            return getattr(pos, attr, 0) or 0

        shares_rc   = get('RC', 'shares')
        cost_rc     = get('RC', 'avg_cost')
        total_rc    = get('RC', 'total_cost')
        shares_hq   = get('華強', 'shares')
        cost_hq     = get('華強', 'avg_cost')
        total_hq    = get('華強', 'total_cost')
        shares_prc  = get('私銀RC', 'shares')
        cost_prc    = get('私銀RC', 'avg_cost')
        total_prc   = get('私銀RC', 'total_cost')
        shares_phq  = get('私銀華強', 'shares')
        cost_phq    = get('私銀華強', 'avg_cost')
        total_phq   = get('私銀華強', 'total_cost')

        pnl_rc   = (price - cost_rc)  * shares_rc   if price and cost_rc  else None
        pnl_hq   = (price - cost_hq)  * shares_hq   if price and cost_hq  else None
        pnl_prc  = (price - cost_prc) * shares_prc  if price and cost_prc else None
        pnl_phq  = (price - cost_phq) * shares_phq  if price and cost_phq else None

        fill = alt_fill if row % 2 == 0 else PatternFill('solid', start_color='FFFFFF')

        values = [
            code,
            data['name'],
            price,
            shares_rc / 1000 if shares_rc else None,
            cost_rc   or None,
            total_rc  or None,
            shares_hq / 1000 if shares_hq else None,
            cost_hq   or None,
            total_hq  or None,
            shares_prc / 1000 if shares_prc else None,
            cost_prc  or None,
            total_prc or None,
            shares_phq / 1000 if shares_phq else None,
            cost_phq  or None,
            total_phq or None,
            pnl_rc,
            pnl_hq,
            pnl_prc,
            pnl_phq,
        ]

        formats = [
            None, None, price_fmt,
            '#,##0.000', price_fmt, num_fmt,
            '#,##0.000', price_fmt, num_fmt,
            '#,##0.000', price_fmt, num_fmt,
            '#,##0.000', price_fmt, num_fmt,
            pnl_fmt, pnl_fmt, pnl_fmt, pnl_fmt,
        ]

        for col, (val, fmt) in enumerate(zip(values, formats), 1):
            cell           = ws.cell(row, col, val)
            cell.font      = normal_font
            cell.fill      = fill
            cell.border    = border
            cell.alignment = right if col > 2 else Alignment(horizontal='left', vertical='center')
            if fmt and val is not None:
                cell.number_format = fmt

        row += 1

    # ── Totals row ───────────────────────────────────────────────────────────
    ws.cell(row, 1, '合計').font      = bold_font
    ws.cell(row, 1).fill              = total_fill
    ws.cell(row, 1).alignment         = center

    total_cols = [6, 9, 12, 15, 16, 17, 18, 19]  # amount + pnl columns
    for c in total_cols:
        if row > 3:
            col_letter = get_column_letter(c)
            formula    = f'=SUM({col_letter}3:{col_letter}{row-1})'
            cell       = ws.cell(row, c, formula)
            cell.font  = bold_font
            cell.fill  = total_fill
            cell.border = border
            cell.alignment = right
            cell.number_format = num_fmt

    # ── Freeze panes ────────────────────────────────────────────────────────
    ws.freeze_panes = 'D3'

    # ── Save ────────────────────────────────────────────────────────────────
    tmp = tempfile.NamedTemporaryFile(
        suffix='.xlsx', delete=False,
        prefix=f'庫存總表_{date.today().strftime("%Y%m%d")}_'
    )
    wb.save(tmp.name)
    return tmp.name
