"""Generate 庫存總表 Excel — fits one page, matches Sophie's layout"""
import tempfile
from datetime import date
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins
from .models import db, Position, Security
from .logic import calculate_realized_pnl

ENTITIES = ['RC', '華強', '私銀RC', '私銀華強']

def _s(ws, row, col, value=None, bold=False, fill=None, num_fmt=None,
       align='right', font_size=9, color='000000', border=None):
    c = ws.cell(row, col, value)
    c.font = Font(name='微軟正黑體', bold=bold, size=font_size, color=color)
    if fill: c.fill = fill
    if num_fmt: c.number_format = num_fmt
    c.alignment = Alignment(horizontal=align, vertical='center', wrap_text=True)
    if border: c.border = border
    return c

def generate_excel() -> str:
    wb = Workbook()
    ws = wb.active
    ws.title = '庫存總表(台灣)'

    # Page setup — fit to 1 page wide, 1 page tall
    ws.page_setup.fitToPage   = True
    ws.page_setup.fitToWidth  = 1
    ws.page_setup.fitToHeight = 1
    ws.page_setup.orientation = 'landscape'
    ws.page_margins = PageMargins(left=0.4, right=0.4, top=0.5, bottom=0.5)

    # Styles
    hdr_fill  = PatternFill('solid', start_color='1F4E79')
    sub_fill  = PatternFill('solid', start_color='2E75B6')
    alt_fill  = PatternFill('solid', start_color='EBF3FB')
    tot_fill  = PatternFill('solid', start_color='BDD7EE')
    pnl_fill  = PatternFill('solid', start_color='E2EFDA')
    grey_fill = PatternFill('solid', start_color='F2F2F2')
    thin      = Side(style='thin', color='B8CCE4')
    bdr       = Border(left=thin, right=thin, top=thin, bottom=thin)
    today_str = date.today().strftime('%Y/%m/%d')

    # Column widths
    col_w = [8, 16, 8,  7,9,11,  7,9,11,  7,9,11,  7,9,11,  11,11,11,11]
    for i, w in enumerate(col_w, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # ── Row 1: Title ──────────────────────────────────────────────────────────
    ws.merge_cells('A1:S1')
    c = ws.cell(1, 1, f'庫存總表（台灣）　　單位：NTD　　日期：{today_str}')
    c.font = Font(name='微軟正黑體', bold=True, size=12)
    c.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 24

    # ── Row 2: Group headers ──────────────────────────────────────────────────
    groups = [(1,1,'股票\n代號'),(2,2,'股票名稱'),(3,3,'市價'),
              (4,6,'RC'),(7,9,'華強'),(10,12,'私RC'),(13,15,'私強'),(16,19,'未實現損益')]
    for cs, ce, label in groups:
        if cs < ce: ws.merge_cells(start_row=2,start_column=cs,end_row=2,end_column=ce)
        c = ws.cell(2, cs, label)
        c.font = Font(name='微軟正黑體', bold=True, size=9, color='FFFFFF')
        c.fill = hdr_fill
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        c.border = bdr
    ws.row_dimensions[2].height = 28

    # ── Row 3: Sub-headers ────────────────────────────────────────────────────
    for col in [1,2,3]:
        ws.merge_cells(start_row=2,start_column=col,end_row=3,end_column=col)
    # Row 3 sub-headers — skip merged cells (cols 1,2,3 are merged with row 2)
    sub_cols = list(range(4, 20))  # cols 4-19 only
    sub_vals = ['張數','成本','金額']*4 + ['RC','華強','私RC','私強']
    for col_i, h in zip(sub_cols, sub_vals):
        c = ws.cell(3, col_i, h)
        c.font = Font(name='微軟正黑體', bold=True, size=9, color='FFFFFF')
        c.fill = sub_fill
        c.alignment = Alignment(horizontal='center', vertical='center')
        c.border = bdr
    ws.row_dimensions[3].height = 18

    # ── Data rows ─────────────────────────────────────────────────────────────
    positions = Position.query.filter(Position.shares > 0).all()
    by_code   = {}
    for pos in positions:
        code = pos.security_code
        if code not in by_code:
            sec = Security.query.get(code)
            by_code[code] = {'name': sec.name if sec else code, 'price': pos.last_price, 'entities': {}}
        by_code[code]['price']            = pos.last_price or by_code[code]['price']
        by_code[code]['entities'][pos.entity] = pos

    realized = calculate_realized_pnl()
    row = 4
    totals = {e: 0 for e in ENTITIES}
    tot_pnl = {e: 0 for e in ENTITIES}

    for code, data in sorted(by_code.items()):
        fill = alt_fill if row % 2 == 0 else PatternFill('solid', start_color='FFFFFF')
        price = data['price']

        _s(ws, row, 1, code,            align='center', bold=True, fill=fill, border=bdr, font_size=9)
        _s(ws, row, 2, data['name'],    align='left',              fill=fill, border=bdr, font_size=9)
        _s(ws, row, 3, price,           align='right',             fill=fill, border=bdr, font_size=9, num_fmt='#,##0.00')

        col = 4
        for ent in ENTITIES:
            pos = data['entities'].get(ent)
            shares = round(pos.shares/1000) if pos else None
            cost   = pos.avg_cost           if pos else None
            total  = round(pos.total_cost)  if pos else None
            pnl    = round(pos.unrealized_pnl()) if (pos and price) else None

            _s(ws, row, col,   shares, fill=fill, border=bdr, font_size=9, num_fmt='#,##0')
            _s(ws, row, col+1, cost,   fill=fill, border=bdr, font_size=9, num_fmt='#,##0.00')
            _s(ws, row, col+2, total,  fill=fill, border=bdr, font_size=9, num_fmt='#,##0')
            if total: totals[ent] += total
            col += 3

        for i, ent in enumerate(ENTITIES):
            pos = data['entities'].get(ent)
            pnl = round(pos.unrealized_pnl()) if (pos and price) else None
            c = ws.cell(row, 16+i, pnl)
            c.font = Font(name='微軟正黑體', size=9,
                         color=('1D9E75' if (pnl or 0) >= 0 else 'C00000'))
            c.fill = fill; c.border = bdr
            c.alignment = Alignment(horizontal='right', vertical='center')
            c.number_format = '+#,##0;-#,##0;-'
            if pnl: tot_pnl[ent] += pnl

        ws.row_dimensions[row].height = 16
        row += 1

    # ── Totals row ────────────────────────────────────────────────────────────
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=3)
    _s(ws, row, 1, '小計', bold=True, align='center', fill=tot_fill, border=bdr)
    col = 4
    for ent in ENTITIES:
        _s(ws, row, col,   None,          fill=tot_fill, border=bdr, font_size=9)
        _s(ws, row, col+1, None,          fill=tot_fill, border=bdr, font_size=9)
        _s(ws, row, col+2, totals[ent],   fill=tot_fill, border=bdr, font_size=9, bold=True, num_fmt='#,##0')
        col += 3
    for i, ent in enumerate(ENTITIES):
        c = ws.cell(row, 16+i, tot_pnl[ent] or None)
        c.font = Font(name='微軟正黑體', bold=True, size=9,
                     color=('1D9E75' if (tot_pnl[ent] or 0) >= 0 else 'C00000'))
        c.fill = tot_fill; c.border = bdr
        c.alignment = Alignment(horizontal='right', vertical='center')
        c.number_format = '+#,##0;-#,##0;-'
    ws.row_dimensions[row].height = 16
    row += 2

    # ── 損益概覽 table ─────────────────────────────────────────────────────────
    # Header
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
    _s(ws, row, 1, '損益', bold=True, align='center', fill=hdr_fill, border=bdr, color='FFFFFF')
    headers2 = [('元大+統一',2), ('私銀(國泰)',2), ('合計',2)]
    col = 3
    for label, span in headers2:
        ws.merge_cells(start_row=row, start_column=col, end_row=row, end_column=col+span-1)
        _s(ws, row, col, label, bold=True, align='center', fill=hdr_fill, border=bdr, color='FFFFFF')
        col += span

    row += 1
    _s(ws, row, 1, '',      fill=sub_fill, border=bdr)
    _s(ws, row, 2, '',      fill=sub_fill, border=bdr)
    # Sub-headers for P&L table
    for i, lbl in enumerate(['RC','華強','RC','華強','RC','華強'], 3):
        c2 = ws.cell(row, i, lbl)
        c2.font = Font(name='微軟正黑體', bold=True, size=9, color='FFFFFF')
        c2.fill = sub_fill
        c2.alignment = Alignment(horizontal='center', vertical='center')
        c2.border = bdr
    row += 1

    uRC  = sum(p.unrealized_pnl() or 0 for p in Position.query.filter_by(entity='RC').filter(Position.shares>0).all())
    uHQ  = sum(p.unrealized_pnl() or 0 for p in Position.query.filter_by(entity='華強').filter(Position.shares>0).all())
    uPRC = sum(p.unrealized_pnl() or 0 for p in Position.query.filter_by(entity='私銀RC').filter(Position.shares>0).all())
    uPHQ = sum(p.unrealized_pnl() or 0 for p in Position.query.filter_by(entity='私銀華強').filter(Position.shares>0).all())
    rRC  = realized.get('RC', 0); rHQ = realized.get('華強', 0)
    rPRC = realized.get('私銀RC', 0); rPHQ = realized.get('私銀華強', 0)

    pnl_rows = [
        ('已實現損益', rRC, rHQ, rPRC, rPHQ),
        ('未實現損益', uRC, uHQ, uPRC, uPHQ),
        ('合計', rRC+uRC, rHQ+uHQ, rPRC+uPRC, rPHQ+uPHQ),
    ]
    for i, (label, rc, hq, prc, phq) in enumerate(pnl_rows):
        fill = tot_fill if i == 2 else pnl_fill
        bold = i == 2
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        _s(ws, row, 1, label, bold=bold, align='left', fill=fill, border=bdr)
        for col_i, val in enumerate([rc, hq, prc, phq, rc+prc, hq+phq], 3):
            c = ws.cell(row, col_i, round(val))
            c.font = Font(name='微軟正黑體', bold=bold, size=9,
                         color=('1D9E75' if val >= 0 else 'C00000'))
            c.fill = fill; c.border = bdr
            c.alignment = Alignment(horizontal='right', vertical='center')
            c.number_format = '+#,##0;-#,##0;-'
        ws.row_dimensions[row].height = 16
        row += 1

    row += 1

    # ── Placeholder sections ──────────────────────────────────────────────────
    placeholders = [
        ('期貨', ['小台指04(空)']),
        ('資金餘額', ['現金', '其他']),
    ]
    for section_name, items in placeholders:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=8)
        _s(ws, row, 1, section_name, bold=True, align='center', fill=grey_fill, border=bdr, font_size=9)
        ws.row_dimensions[row].height = 14
        row += 1
        for item in items:
            _s(ws, row, 1, item, align='left', fill=PatternFill('solid', start_color='FFFFFF'), border=bdr, font_size=9)
            _s(ws, row, 2, '(待補)', align='center', fill=PatternFill('solid', start_color='FFFFFF'), border=bdr,
               font_size=8, color='AAAAAA')
            ws.row_dimensions[row].height = 14
            row += 1
        row += 1

    ws.freeze_panes = 'D4'

    tmp = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False,
        prefix=f'庫存總表_{date.today().strftime("%Y%m%d")}_')
    wb.save(tmp.name)
    return tmp.name
