"""Generate 庫存總表 Excel — matches Sophie's reference layout exactly"""
import tempfile
from datetime import date
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins
from .models import db, Position, Security, CashAccount
from .logic import calculate_realized_pnl

ENTITIES = ['RC', '華強', '私銀RC', '私銀華強']

# ── Helpers ───────────────────────────────────────────────────────────────────
def _thin_border():
    t = Side(style='thin', color='000000')
    return Border(left=t, right=t, top=t, bottom=t)

def _cell(ws, row, col, value=None, font_size=16, bold=False,
          align='center', valign='center', wrap=False,
          num_fmt=None, color='000000', border=False):
    c = ws.cell(row, col, value)
    c.font      = Font(name='微軟正黑體', size=font_size, bold=bold, color=color)
    c.alignment = Alignment(horizontal=align, vertical=valign,
                            wrap_text=wrap)
    if num_fmt:
        c.number_format = num_fmt
    if border:
        c.border = _thin_border()
    return c

def generate_excel() -> str:
    wb = Workbook()
    ws = wb.active
    ws.title = '庫存總表(台灣)'

    # ── Page setup ────────────────────────────────────────────────────────────
    ws.page_setup.paperSize   = 9          # A4
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToPage   = True
    ws.page_setup.fitToWidth  = 1
    ws.page_setup.fitToHeight = 1
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_margins = PageMargins(left=2/2.54, right=2/2.54,
                                  top=2.3/2.54, bottom=2.3/2.54,
                                  header=0.8/2.54, footer=0.8/2.54)

    # ── Column widths (from reference file) ───────────────────────────────────
    col_w = {
        'A': 11, 'B': 22, 'C': 26.5, 'D': 12, 'E': 24, 'F': 24,
        'G': 12, 'H': 20, 'I': 26.5, 'J': 12, 'K': 21.7, 'L': 23.3,
        'M': 12, 'N': 24, 'O': 25.7, 'P': 21.7, 'Q': 19.7,
        'R': 19.7, 'S': 9.1
    }
    for col, w in col_w.items():
        ws.column_dimensions[col].width = w

    today_str = date.today().strftime('%Y/%m/%d')

    # ── Row 1: Title ──────────────────────────────────────────────────────────
    ws.merge_cells('A1:S1')
    _cell(ws, 1, 1, f'庫存總表（台灣）　　單位：NTD　　日期：{today_str}',
          font_size=28, bold=True, align='center')
    ws.row_dimensions[1].height = 88.5

    # ── Row 2: Group headers ──────────────────────────────────────────────────
    # Merge A2:A3, B2:B3, C2:C3
    for col in ['A', 'B', 'C']:
        ws.merge_cells(f'{col}2:{col}3')
    labels_r2 = [('A2','A3','股票\n代號'), ('B2','B3','股票名稱'), ('C2','C3','市價'),
                 ('D2','F2','RC'), ('G2','I2','華強'), ('J2','L2','私RC'),
                 ('M2','O2','私強'), ('P2','S2','未實現損益')]
    for start, end, label in labels_r2:
        if start != end:
            ws.merge_cells(f'{start}:{end}')
        sc = ws[start]
        sc.value     = label
        sc.font      = Font(name='微軟正黑體', size=16, bold=True)
        sc.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        sc.border    = _thin_border()
    ws.row_dimensions[2].height = 36

    # ── Row 3: Sub-headers ────────────────────────────────────────────────────
    sub_headers = {
        4:'張數', 5:'成本', 6:'金額',
        7:'張數', 8:'成本', 9:'金額',
        10:'張數', 11:'成本', 12:'金額',
        13:'張數', 14:'成本', 15:'金額',
        16:'RC', 17:'華強', 18:'私RC', 19:'私強'
    }
    for col_i, label in sub_headers.items():
        c = ws.cell(3, col_i, label)
        c.font      = Font(name='微軟正黑體', size=16, bold=True)
        c.alignment = Alignment(horizontal='center', vertical='center')
        c.border    = _thin_border()
    ws.row_dimensions[3].height = 51

    # ── Data rows ─────────────────────────────────────────────────────────────
    positions = Position.query.filter(Position.shares > 0).all()
    by_code   = {}
    for pos in positions:
        code = pos.security_code
        if code not in by_code:
            sec = Security.query.get(code)
            by_code[code] = {'name': sec.name if sec else code,
                             'price': pos.last_price, 'entities': {}}
        by_code[code]['price'] = pos.last_price or by_code[code]['price']
        by_code[code]['entities'][pos.entity] = pos

    realized = calculate_realized_pnl()
    row = 4
    totals  = {e: 0 for e in ENTITIES}
    tot_pnl = {e: 0 for e in ENTITIES}

    ROW_HEIGHTS = [67.5, 76.5, 69.75, 81.75, 84.0, 67.5]

    for idx, (code, data) in enumerate(sorted(by_code.items())):
        price = data['price']

        # Code + name (bold 16), price (20)
        _cell(ws, row, 1, code,           font_size=16, bold=True,  align='center', border=True)
        _cell(ws, row, 2, data['name'],   font_size=16, bold=True,  align='left',   border=True)
        _cell(ws, row, 3, price,          font_size=20, bold=False, align='right',  border=True,
              num_fmt='#,##0.00')

        # Entity columns (cols 4-15): 張數, 成本, 金額
        col = 4
        for ent in ENTITIES:
            pos    = data['entities'].get(ent)
            shares = (pos.shares / 1000) if pos else None
            if shares is not None:
                shares = float(f'{shares:.3f}'.rstrip('0').rstrip('.'))
            cost   = pos.avg_cost          if pos else None
            total  = round(pos.total_cost) if pos else None

            _cell(ws, row, col,   shares, font_size=20, align='right', border=True, num_fmt='#,##0.##')
            _cell(ws, row, col+1, cost,   font_size=20, align='right', border=True, num_fmt='#,##0.00')
            _cell(ws, row, col+2, total,  font_size=20, align='right', border=True, num_fmt='#,##0')
            if total: totals[ent] += total
            col += 3

        # Unrealized P&L (cols 16-19)
        for i, ent in enumerate(ENTITIES):
            pos = data['entities'].get(ent)
            pnl = round(pos.unrealized_pnl()) if (pos and price) else None
            c = ws.cell(row, 16 + i, pnl)
            clr = 'C00000' if (pnl or 0) < 0 else '000000'
            c.font         = Font(name='微軟正黑體', size=20, color=clr)
            c.alignment    = Alignment(horizontal='right', vertical='center')
            c.number_format = '#,##0'
            c.border       = _thin_border()
            if pnl: tot_pnl[ent] += pnl

        # Draw borders on ALL cells in the row (including empty ones) for clean grid
        for col_i in range(1, 20):
            c = ws.cell(row, col_i)
            if c.border.left.style is None:
                c.border = _thin_border()

        ws.row_dimensions[row].height = ROW_HEIGHTS[idx % len(ROW_HEIGHTS)]
        row += 1

    # ── Totals row ────────────────────────────────────────────────────────────
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
    _cell(ws, row, 1, '小計', font_size=16, bold=True, align='left', border=True)
    col = 4
    for ent in ENTITIES:
        _cell(ws, row, col,   None,         font_size=20, border=True)
        _cell(ws, row, col+1, None,         font_size=20, border=True)
        _cell(ws, row, col+2, totals[ent],  font_size=20, bold=True, align='right',
              border=True, num_fmt='#,##0')
        col += 3
    for i, ent in enumerate(ENTITIES):
        val = tot_pnl[ent] or None
        c = ws.cell(row, 16+i, val)
        clr = 'C00000' if (val or 0) < 0 else '000000'
        c.font         = Font(name='微軟正黑體', size=20, bold=True, color=clr)
        c.alignment    = Alignment(horizontal='right', vertical='center')
        c.number_format = '#,##0'
        c.border       = _thin_border()
    # Borders on all totals row cells
    for col_i in range(1, 20):
        c = ws.cell(row, col_i)
        if c.border.left.style is None:
            c.border = _thin_border()
    ws.row_dimensions[row].height = 51
    row += 2

    # ── 損益 table ─────────────────────────────────────────────────────────────
    ws.merge_cells(start_row=row, start_column=1, end_row=row+1, end_column=2)
    _cell(ws, row, 1, '損益', font_size=16, bold=True, align='center', border=True)

    for label, cs, ce in [('元大+統一',3,4), ('私銀(國泰)',5,6), ('合計',7,8)]:
        ws.merge_cells(start_row=row, start_column=cs, end_row=row, end_column=ce)
        c = ws.cell(row, cs, label)
        c.font      = Font(name='微軟正黑體', size=16, bold=True)
        c.alignment = Alignment(horizontal='center', vertical='center')
        c.border    = _thin_border()

    ws.row_dimensions[row].height = 50
    row += 1

    for col_i, label in [(3,'RC'),(4,'華強'),(5,'RC'),(6,'華強'),(7,'RC'),(8,'華強')]:
        c = ws.cell(row, col_i, label)
        c.font      = Font(name='微軟正黑體', size=16, bold=True)
        c.alignment = Alignment(horizontal='center', vertical='center')
        c.border    = _thin_border()
    ws.row_dimensions[row].height = 50
    row += 1

    uRC  = sum(p.unrealized_pnl() or 0 for p in Position.query.filter_by(entity='RC').filter(Position.shares>0).all())
    uHQ  = sum(p.unrealized_pnl() or 0 for p in Position.query.filter_by(entity='華強').filter(Position.shares>0).all())
    uPRC = sum(p.unrealized_pnl() or 0 for p in Position.query.filter_by(entity='私銀RC').filter(Position.shares>0).all())
    uPHQ = sum(p.unrealized_pnl() or 0 for p in Position.query.filter_by(entity='私銀華強').filter(Position.shares>0).all())
    rRC  = realized.get('RC', 0);    rHQ  = realized.get('華強', 0)
    rPRC = realized.get('私銀RC', 0); rPHQ = realized.get('私銀華強', 0)

    pnl_rows = [
        ('已實現損益', rRC, rHQ, rPRC, rPHQ),
        ('未實現損益', uRC, uHQ, uPRC, uPHQ),
        ('合計', rRC+uRC, rHQ+uHQ, rPRC+uPRC, rPHQ+uPHQ),
    ]
    for label, rc, hq, prc, phq in pnl_rows:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        _cell(ws, row, 1, label, font_size=16, bold=True, align='left', border=True)
        for col_i, val in enumerate([rc, hq, prc, phq, rc+prc, hq+phq], 3):
            clr = 'C00000' if val < 0 else '000000'
            c = ws.cell(row, col_i, round(val))
            c.font         = Font(name='微軟正黑體', size=20, color=clr)
            c.alignment    = Alignment(horizontal='right', vertical='center')
            c.number_format = '#,##0'
            c.border       = _thin_border()
        ws.row_dimensions[row].height = 69
        row += 1

    row += 1

    # ── 資金餘額 section ───────────────────────────────────────────────────────
    # Header
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
    _cell(ws, row, 1, '賬戶',   font_size=16, bold=True, align='center', border=True)
    ws.merge_cells(start_row=row, start_column=3, end_row=row, end_column=8)
    _cell(ws, row, 3, '資金餘額', font_size=16, bold=True, align='center', border=True)
    ws.row_dimensions[row].height = 51
    row += 1

    # Pull balances from CashAccount — sum by entity
    # Cash accounts: all are under entity RC or 華強
    # RC non-private accounts: rc_dunnan, rc_tuni, rc_yuanta, rc_fund, rc_other
    # RC private: rc_private
    # 華強 non-private: hq_tuni, hq_yuanta, hq_dunnan, hq_fund, hq_huanan, hq_fubon, hq_yuanta_bank
    # 華強 private: hq_private
    RC_PRIVATE    = {'rc_private'}
    HQ_PRIVATE    = {'hq_private'}
    RC_NON_PRIV   = {'rc_dunnan','rc_tuni','rc_yuanta','rc_fund','rc_other'}
    HQ_NON_PRIV   = {'hq_tuni','hq_yuanta','hq_dunnan','hq_fund','hq_huanan','hq_fubon','hq_yuanta_bank'}

    entity_balance = {'RC': 0, '華強': 0, '私RC': 0, '私強': 0}
    accounts = CashAccount.query.all()
    for acct in accounts:
        bal = acct.balance or 0
        if acct.id in RC_NON_PRIV:
            entity_balance['RC'] += bal
        elif acct.id in RC_PRIVATE:
            entity_balance['私RC'] += bal
        elif acct.id in HQ_NON_PRIV:
            entity_balance['華強'] += bal
        elif acct.id in HQ_PRIVATE:
            entity_balance['私強'] += bal

    display_labels = [('RC','RC'), ('華強','華強'), ('私RC','私RC'), ('私強','私華強')]
    for ent_key, ent_label in display_labels:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        _cell(ws, row, 1, ent_label, font_size=16, bold=True, align='left', border=True)
        ws.merge_cells(start_row=row, start_column=3, end_row=row, end_column=8)
        bal = round(entity_balance.get(ent_key, 0))
        c = ws.cell(row, 3, bal)
        c.font         = Font(name='微軟正黑體', size=20)
        c.alignment    = Alignment(horizontal='right', vertical='center')
        c.number_format = '#,##0'
        c.border       = _thin_border()
        ws.row_dimensions[row].height = 54
        row += 1

    # No freeze panes

    tmp = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False,
        prefix=f'庫存總表_{date.today().strftime("%Y%m%d")}_')
    wb.save(tmp.name)
    return tmp.name
