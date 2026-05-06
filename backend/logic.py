"""
Business logic:
  - Recalculate positions from transaction history
  - Fetch live prices from TWSE public API
"""

import requests
from datetime import date, datetime
from .models import db, Transaction, Position, Security, ACCOUNT_MAP


# ── Position calculation ─────────────────────────────────────────────────────

def recalculate_positions(entity: str = None):
    """
    Recalculate all positions from transaction history.
    If entity specified, only recalculate that entity.
    Uses FIFO average cost method.
    """
    entities = [entity] if entity else list({v['entity'] for v in ACCOUNT_MAP.values()})

    for ent in entities:
        # Get all buy/sell transactions for this entity, ordered by date
        txns = (Transaction.query
                .filter_by(entity=ent)
                .filter(Transaction.security_code.isnot(None))
                .filter(Transaction.shares != 0)
                .order_by(Transaction.trade_date)
                .all())

        # Group by security
        holdings = {}  # code → {shares, total_cost}
        for txn in txns:
            code = txn.security_code
            if code not in holdings:
                holdings[code] = {'shares': 0.0, 'total_cost': 0.0}

            if txn.shares > 0:
                # Buy: add to cost basis
                holdings[code]['shares']     += txn.shares
                holdings[code]['total_cost'] += txn.gross_amount + txn.fee
            else:
                # Sell: reduce proportionally
                if holdings[code]['shares'] > 0:
                    sell_qty  = abs(txn.shares)
                    avg       = holdings[code]['total_cost'] / holdings[code]['shares']
                    cost_reduction = avg * sell_qty
                    holdings[code]['shares']     -= sell_qty
                    holdings[code]['total_cost'] -= cost_reduction
                    # Floor at zero to handle rounding
                    if holdings[code]['shares'] < 0.001:
                        holdings[code]['shares']     = 0
                        holdings[code]['total_cost'] = 0

        # Write to Position table
        for code, data in holdings.items():
            shares = data['shares']
            cost   = data['total_cost']

            pos = Position.query.filter_by(entity=ent, security_code=code).first()
            if pos is None:
                pos = Position(entity=ent, security_code=code)
                db.session.add(pos)

            pos.shares     = round(shares, 4)
            pos.total_cost = round(cost, 4)
            pos.avg_cost   = round(cost / shares, 4) if shares > 0 else 0

        # Remove zero positions that are no longer held
        zero_positions = (Position.query
                          .filter_by(entity=ent)
                          .filter(Position.shares <= 0)
                          .all())
        for zp in zero_positions:
            db.session.delete(zp)

    db.session.commit()


# ── TWSE Price Fetcher ───────────────────────────────────────────────────────

TWSE_URL = 'https://mis.twse.com.tw/stock/api/getStockInfo.jsp'
TWSE_HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Referer': 'https://mis.twse.com.tw/',
}

def fetch_twse_price(code: str) -> dict:
    """
    Fetch latest price for a single stock from TWSE.
    Returns {'code': ..., 'name': ..., 'price': ..., 'date': ...}
    Handles both listed (tse_) and OTC (otc_) stocks.
    """
    for prefix in ['tse_', 'otc_']:
        try:
            params = {'ex_ch': f'{prefix}{code}.tw', 'json': 1, 'delay': 0}
            resp   = requests.get(TWSE_URL, params=params,
                                  headers=TWSE_HEADERS, timeout=5)
            data   = resp.json()
            msgArray = data.get('msgArray', [])
            if msgArray:
                item  = msgArray[0]
                price = item.get('z', '-')   # current/last price
                if price == '-':
                    price = item.get('y', '-')  # yesterday's close
                if price != '-':
                    return {
                        'code':  code,
                        'name':  item.get('n', ''),
                        'price': float(price),
                        'date':  date.today(),
                    }
        except Exception:
            continue
    return {'code': code, 'name': '', 'price': None, 'date': None}


def fetch_twse_name(code: str) -> str:
    """Just get the stock name from TWSE (for new security confirmation)"""
    result = fetch_twse_price(code)
    return result.get('name', '')


def update_all_prices():
    """
    Fetch latest prices for all securities with active positions.
    Returns list of {code, name, old_price, new_price, status}
    """
    # Get all codes with non-zero positions
    active_codes = (db.session.query(Position.security_code)
                    .filter(Position.shares > 0)
                    .distinct()
                    .all())
    codes   = [row[0] for row in active_codes]
    results = []

    for code in codes:
        fetch  = fetch_twse_price(code)
        sec    = Security.query.get(code)
        old_px = None

        # Update all positions for this security
        positions = Position.query.filter_by(security_code=code).all()
        for pos in positions:
            old_px = pos.last_price
            if fetch['price']:
                pos.last_price  = fetch['price']
                pos.price_date  = fetch['date']

        # Update security name if TWSE returned one
        if sec and fetch['name'] and not sec.name:
            sec.name = fetch['name']

        results.append({
            'code':      code,
            'name':      sec.name if sec else code,
            'old_price': old_px,
            'new_price': fetch['price'],
            'status':    'updated' if fetch['price'] else 'failed',
        })

    db.session.commit()
    return results
