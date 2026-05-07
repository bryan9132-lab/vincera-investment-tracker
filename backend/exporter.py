"""Generate 庫存總表 Excel for Richard"""
import tempfile
from datetime import date
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from .models import db, Position, Security

ENTITIES = ['RC','華強','私銀RC','私銀華強']

def generate_excel() -> str:
    wb = Workbook()
    ws = wb.active
    ws.title = '庫存總表(台灣)'

    hdr_font  = Font(name='微軟正黑體', bold=True, size=10, color='FFFFFF')
    hdr_fill  = PatternFill('solid', start_color='1F4E79')
    sub_fill  = PatternFill('solid', start_color='2E75B6')
    alt_fill  = PatternFill('solid', start_color='EBF3FB')
    tot_fill  = PatternFill('solid', start_color='BDD7EE')
    bold_font = Font(name='微軟正黑體', bold=True, size=10)
    norm_font = Font(name='微軟正黑體', size=10)
    center    = Alignment(horizontal='center', vertical='center', wrap_text=True)
    left_al   = Alignment(horizontal='left', vertical='center')
    right_al  = Alignment(horizontal='right', vertical='center')
    thin      = Side(style='thin', color='B8CCE4')
    bdr       = Border(left=thin, right=thin, top=thin, bottom=thin)
    num_fmt   = '#,##0'
    price_fmt = '#,##0.00'
    pnl_fmt   = '+#,##0;-#,##0;-'
    today_str = date.today().strftime('%Y/%m/%d')

    # Title
    ws.merge_cells('A1:S1')
    ws['A1'] = f'庫存總表（台灣）　　單位：NTD　　日期：{today_str}'
    ws['A1'].font = Font(name='微軟正黑體', bold=True, size=13)
    ws['A1'].alignment = center
    ws.row_dimensions[1].height = 30

    # Row 2: group headers (merged)
    groups = [(1,1,'股票代號'),(2,2,'股票名稱'),(3,3,'市價'),
              (4,6,'RC'),(7,9,'華強'),(10,12,'私RC'),(13,15,'私強'),(16,19,'未實現損益')]
    for cs, ce, label in groups:
        if cs < ce:
            ws.merge_cells(start_row=2,start_column=cs,end_row=2,end_column=ce)
        c = ws.cell(2, cs, label)
        c.font=hdr_font; c.fill=hdr_fill; c.alignment=center; c.border=bdr
    ws.row_dimensions[2].height = 22

    # Row 3: sub-headers
    row3 = ['','',''] + ['張數','每股成本','金額']*4 + ['RC','華強','私RC','私強']
    for i, h in enumerate(row3, 1):
        c = ws.cell(3, i, h)
        c.font=hdr_font if h else norm_font
        c.fill=sub_fill if h else hdr_fill
        c.alignment=center; c.border=bdr
    # Merge A-C rows 2-3 for fixed headers
    for col in [1,2,3]:
        ws.merge_cells(start_row=2,start_column=col,end_row=3,end_column=col)
    ws.row_dimensions[3].height = 22

    # Column widths
    for i,w in enumerate([10,28,10,8,10,12,8,10,12,8,10,12,8,10,12,12,12,12,12],1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # Data
    positions = Position.query.filter(Position.shares > 0).all()
    by_code = {}
    for pos in positions:
        code = pos.security_code
        if code not in by_code:
            sec = Security.query.get(code)
            by_code[code] = {'name': sec.name if sec else code, 'last_price': pos.last_price, 'entities': {}}
        by_code[code]['last_price'] = pos.last_price
        by_code[code]['entities'][pos.entity] = pos

    row = 4
    total_cols = {e:0 for e in ENTITIES}
    total_pnl  = {e:0 for e in ENTITIES}

    for code, data in sorted(by_code.items()):
        price = data['last_price']
        ents  = data['entities']
        fill  = alt_fill if row%2==0 else PatternFill('solid',start_color='FFFFFF')

        def set_cell(c, v, fmt=None, fnt=None, al=right_al):
            cell = ws.cell(row, c, v)
            cell.font=fnt or norm_font; cell.fill=fill; cell.border=bdr; cell.alignment=al
            if fmt: cell.number_format=fmt

        set_cell(1, code, al=left_al)
        set_cell(2, data['name'], al=left_al)
        set_cell(3, price, price_fmt)

        col = 4
        for ent in ENTITIES:
            pos = ents.get(ent)
            shares = pos.shares if pos else None
            cost   = pos.avg_cost if pos else None
            total  = pos.total_cost if pos else None
            set_cell(col,   round(shares/1000) if shares else None, num_fmt)
            set_cell(col+1, cost, price_fmt)
            set_cell(col+2, round(total) if total else None, num_fmt)
            if total: total_cols[ent] += round(total)
            col += 3

        for ent in ENTITIES:
            pos = ents.get(ent)
            pnl = pos.unrealized_pnl() if pos else None
            c = ws.cell(row, col)
            c.value=round(pnl) if pnl is not None else None
            c.font=norm_font; c.fill=fill; c.border=bdr; c.alignment=right_al
            c.number_format=pnl_fmt
            if pnl: total_pnl[ent] += round(pnl)
            col += 1
        row += 1

    # Totals
    for c in range(1,20):
        cell = ws.cell(row, c)
        cell.fill=tot_fill; cell.border=bdr; cell.font=bold_font
    ws.cell(row,1,'合計').alignment=center

    col=4
    for ent in ENTITIES:
        c=ws.cell(row,col+2,total_cols[ent])
        c.number_format=num_fmt; c.font=bold_font; c.fill=tot_fill; c.border=bdr; c.alignment=right_al
        col+=3
    for i,ent in enumerate(ENTITIES):
        c=ws.cell(row,16+i,total_pnl[ent])
        c.number_format=pnl_fmt; c.font=bold_font; c.fill=tot_fill; c.border=bdr; c.alignment=right_al

    ws.freeze_panes='D4'
    tmp=tempfile.NamedTemporaryFile(suffix='.xlsx',delete=False,prefix=f'庫存總表_{date.today().strftime("%Y%m%d")}_')
    wb.save(tmp.name)
    return tmp.name
