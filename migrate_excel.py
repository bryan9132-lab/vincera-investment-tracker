"""
migrate_excel.py
----------------
One-time script to import all historical transaction data from Sophie's Excel
into the VIT database.

Usage:
    python migrate_excel.py path/to/test-20260505.xlsx
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import openpyxl
from datetime import datetime, date
from backend.app import create_app
from backend.models import db, Transaction, Position, Security, ACCOUNT_MAP
from backend.logic import recalculate_positions


def parse_date(val) -> date:
    if val is None:
        return None
    if isinstance(val, (datetime,)):
        return val.date()
    if isinstance(val, date):
        return val
    return None


def safe_float(val) -> float:
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(str(val).replace(',', ''))
    except Exception:
        return 0.0


def is_real_value(val) -> bool:
    if val is None:
        return False
    s = str(val)
    return not s.startswith('=') and s not in ['', '0', '0.0']


def migrate_rc_tuni(ws, app):
    """(RC)統一進出明細TWD — cols: A=date, C=code, E=shares, F=price, G=gross, H=fee, I=tax, K=net"""
    trades = []
    for r in range(2, ws.max_row + 1):
        trade_date = parse_date(ws.cell(r, 1).value)
        code       = ws.cell(r, 3).value
        shares     = ws.cell(r, 5).value
        price      = ws.cell(r, 6).value
        gross      = ws.cell(r, 7).value
        fee        = ws.cell(r, 8).value
        tax        = ws.cell(r, 9).value
        net        = ws.cell(r, 11).value

        if not trade_date or not code or not is_real_value(shares):
            continue
        if str(code).startswith('=') or str(shares).startswith('='):
            continue
        if str(code) in ['期初', '合計', '資金調撥']:
            continue

        trades.append({
            'trade_date': trade_date,
            'entity': 'RC', 'broker': '統一', 'account_no': '600826',
            'security_code': str(code).strip(),
            'shares': safe_float(shares),
            'price': safe_float(price),
            'gross_amount': abs(safe_float(gross)),
            'fee': safe_float(fee),
            'tax': safe_float(tax),
            'net_amount': abs(safe_float(net)),
        })
    return trades


def migrate_rc_yuanta(ws, app):
    """(RC)元大進出明細TWD — cols: A=date, C=code, E=shares, J=gross(cost), H=fee, I=tax, K=net"""
    trades = []
    for r in range(2, ws.max_row + 1):
        trade_date = parse_date(ws.cell(r, 1).value)
        code       = ws.cell(r, 3).value
        shares     = ws.cell(r, 5).value
        gross      = ws.cell(r, 10).value  # investment cost col J
        fee        = ws.cell(r, 8).value
        tax        = ws.cell(r, 9).value
        net        = ws.cell(r, 11).value
        price      = ws.cell(r, 6).value   # may be None for opening positions

        if not trade_date or not code or not is_real_value(shares):
            continue
        if str(code).startswith('=') or str(shares).startswith('='):
            continue
        if str(code) in ['期初餘額', '期初', '合計', '資金調撥', '匯款', '匯費']:
            continue
        try:
            int(str(code))  # must be numeric stock code
        except ValueError:
            continue

        gross_val  = abs(safe_float(gross))
        shares_val = safe_float(shares)
        price_val  = safe_float(price) if price else (gross_val / shares_val if shares_val else 0)

        trades.append({
            'trade_date': trade_date,
            'entity': 'RC', 'broker': '元大', 'account_no': '133376',
            'security_code': str(code).strip(),
            'shares': shares_val,
            'price': price_val,
            'gross_amount': gross_val,
            'fee': safe_float(fee),
            'tax': safe_float(tax),
            'net_amount': abs(safe_float(net)),
        })
    return trades


def migrate_hq_tuni(ws, app):
    """(華強)統一進出明細TWD — cols: C=date, D=code, F=shares, G=price, H=gross, I=fee, J=tax, L=net"""
    trades = []
    for r in range(2, ws.max_row + 1):
        trade_date = parse_date(ws.cell(r, 3).value)
        code       = ws.cell(r, 4).value
        shares     = ws.cell(r, 6).value
        price      = ws.cell(r, 7).value
        gross      = ws.cell(r, 8).value
        fee        = ws.cell(r, 9).value
        tax        = ws.cell(r, 10).value
        net        = ws.cell(r, 13).value

        if not trade_date or not code or not is_real_value(shares):
            continue
        if str(code).startswith('=') or str(shares).startswith('='):
            continue
        if str(code) in ['期初', '合計', '資金調撥', '總計(SUM)'] or str(code).startswith('私銀'):
            continue
        try:
            int(str(code).replace('A', '').replace('L', ''))
        except ValueError:
            continue

        trades.append({
            'trade_date': trade_date,
            'entity': '華強', 'broker': '統一', 'account_no': '600885',
            'security_code': str(code).strip(),
            'shares': safe_float(shares),
            'price': safe_float(price),
            'gross_amount': abs(safe_float(gross)),
            'fee': safe_float(fee),
            'tax': safe_float(tax),
            'net_amount': abs(safe_float(net)),
        })
    return trades


def migrate_hq_yuanta(ws, app):
    """(華強)元大進出明細TWD — cols: C=date, D=code, F=shares, K=gross, I=fee, J=tax"""
    trades = []
    for r in range(2, ws.max_row + 1):
        trade_date = parse_date(ws.cell(r, 3).value)
        code       = ws.cell(r, 4).value
        shares     = ws.cell(r, 6).value
        gross      = ws.cell(r, 11).value
        fee        = ws.cell(r, 9).value
        tax        = ws.cell(r, 10).value
        net        = ws.cell(r, 12).value
        price      = ws.cell(r, 7).value

        if not trade_date or not code or not is_real_value(shares):
            continue
        if str(code).startswith('=') or str(shares).startswith('='):
            continue
        if str(code) in ['期初', '合計', '資金調撥'] or not str(code).strip():
            continue
        try:
            int(str(code))
        except ValueError:
            continue

        gross_val  = abs(safe_float(gross))
        shares_val = safe_float(shares)
        price_val  = safe_float(price) if price else (gross_val / shares_val if shares_val else 0)

        trades.append({
            'trade_date': trade_date,
            'entity': '華強', 'broker': '元大', 'account_no': '133311',
            'security_code': str(code).strip(),
            'shares': shares_val,
            'price': price_val,
            'gross_amount': gross_val,
            'fee': safe_float(fee),
            'tax': safe_float(tax),
            'net_amount': abs(safe_float(net)),
        })
    return trades


def migrate_private_rc(ws, app):
    """(私RC)TWD — cols: A=date, C=code, F=shares, G=price, H=gross, I=fee, J=tax, M=net"""
    trades = []
    for r in range(2, ws.max_row + 1):
        trade_date = parse_date(ws.cell(r, 1).value)
        code       = ws.cell(r, 3).value
        shares     = ws.cell(r, 6).value
        price      = ws.cell(r, 7).value
        gross      = ws.cell(r, 8).value
        fee        = ws.cell(r, 9).value
        tax        = ws.cell(r, 10).value
        net        = ws.cell(r, 13).value

        if not trade_date or not code or not is_real_value(shares):
            continue
        if str(code).startswith('=') or str(shares).startswith('='):
            continue
        if str(code) in ['期初', '合計', '資金調撥', '賣美金', '買美金']:
            continue

        trades.append({
            'trade_date': trade_date,
            'entity': '私銀RC', 'broker': '國泰', 'account_no': '006439',
            'security_code': str(code).strip(),
            'shares': safe_float(shares),
            'price': safe_float(price),
            'gross_amount': abs(safe_float(gross)),
            'fee': safe_float(fee),
            'tax': safe_float(tax),
            'net_amount': abs(safe_float(net)),
        })
    return trades


def migrate_private_hq(ws, app):
    """(私強)進出明細TWD — cols: C=date, E=code, H=shares, I=price, J=gross, K=fee, L=tax"""
    trades = []
    for r in range(2, ws.max_row + 1):
        trade_date = parse_date(ws.cell(r, 3).value)
        code       = ws.cell(r, 5).value
        shares     = ws.cell(r, 8).value
        price      = ws.cell(r, 9).value
        gross      = ws.cell(r, 10).value
        fee        = ws.cell(r, 11).value
        tax        = ws.cell(r, 12).value

        if not trade_date or not code or not is_real_value(shares):
            continue
        if str(code).startswith('=') or str(shares).startswith('='):
            continue
        if str(code) in ['期初', '合計', '資金調撥', '損益總計']:
            continue

        gross_val  = abs(safe_float(gross))
        shares_val = safe_float(shares)

        trades.append({
            'trade_date': trade_date,
            'entity': '私銀華強', 'broker': '國泰', 'account_no': '007065',
            'security_code': str(code).strip(),
            'shares': shares_val,
            'price': safe_float(price),
            'gross_amount': gross_val,
            'fee': safe_float(fee),
            'tax': safe_float(tax),
            'net_amount': gross_val,  # net not separately stored in this sheet
        })
    return trades


def run_migration(excel_path: str):
    app = create_app()

    with app.app_context():
        # Clear existing transactions (fresh migration)
        existing = Transaction.query.count()
        if existing > 0:
            print(f'⚠ Database already has {existing} transactions.')
            confirm = input('Clear and re-migrate? (yes/no): ')
            if confirm.lower() != 'yes':
                print('Migration cancelled.')
                return
            Transaction.query.delete()
            Position.query.delete()
            db.session.commit()
            print('Cleared existing data.')

        wb = openpyxl.load_workbook(excel_path, data_only=True)

        sheet_handlers = [
            ('(RC)統一進出明細TWD',   migrate_rc_tuni),
            ('(RC)元大進出明細TWD',   migrate_rc_yuanta),
            ('(華強)統一進出明細TWD', migrate_hq_tuni),
            ('(華強)元大進出明細TWD', migrate_hq_yuanta),
            ('(私RC)TWD',            migrate_private_rc),
            ('(私強)進出明細TWD',     migrate_private_hq),
        ]

        total = 0
        for sheet_name, handler in sheet_handlers:
            ws     = wb[sheet_name]
            trades = handler(ws, app)
            print(f'{sheet_name}: {len(trades)} trades')

            for t in trades:
                # Ensure security exists
                code = t['security_code']
                if code and not Security.query.get(code):
                    db.session.add(Security(code=code, name=code))  # name filled later by TWSE

                txn = Transaction(
                    trade_date    = t['trade_date'],
                    entity        = t['entity'],
                    broker        = t['broker'],
                    account_no    = t['account_no'],
                    security_code = t['security_code'],
                    shares        = t['shares'],
                    price         = t['price'],
                    gross_amount  = t['gross_amount'],
                    fee           = t['fee'],
                    tax           = t['tax'],
                    net_amount    = t['net_amount'],
                    source_file   = os.path.basename(excel_path),
                )
                db.session.add(txn)
                total += 1

        db.session.commit()
        print(f'\n✅ Migrated {total} transactions total')

        # Recalculate all positions
        print('Recalculating positions...')
        recalculate_positions()
        print('✅ Positions calculated')

        # Summary
        from backend.models import Position
        positions = Position.query.filter(Position.shares > 0).all()
        print(f'\nCurrent holdings: {len(positions)} positions')
        for p in positions:
            print(f'  {p.entity} | {p.security_code} | {p.shares:,.0f} shares | avg cost {p.avg_cost:.2f}')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python migrate_excel.py path/to/excel.xlsx')
        sys.exit(1)
    run_migration(sys.argv[1])
