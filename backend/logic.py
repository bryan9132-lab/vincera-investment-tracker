"""
Business logic:
  - Recalculate positions from transaction history
  - Fetch live prices via Yahoo Finance (works globally)
"""

import requests
from datetime import date, datetime, timedelta
from .models import db, Transaction, Position, Security, ACCOUNT_MAP


def recalculate_positions(entity: str = None):
    entities = [entity] if entity else list({v['entity'] for v in ACCOUNT_MAP.values()})

    for ent in entities:
        txns = (Transaction.query
                .filter_by(entity=ent)
                .filter(Transaction.security_code.isnot(None))
                .filter(Transaction.shares != 0)
                .order_by(Transaction.trade_date)
                .all())

        holdings = {}
        for txn in txns:
            code = txn.security_code
            if code not in holdings:
                holdings[code] = {'shares': 0.0, 'total_cost': 0.0}
            if txn.shares > 0:
                holdings[code]['shares']     += txn.shares
                holdings[code]['total_cost'] += txn.gross_amount + txn.fee
            else:
                if holdings[code]['shares'] > 0:
                    sell_qty       = abs(txn.shares)
                    avg            = holdings[code]['total_cost'] / holdings[code]['shares']
                    holdings[code]['shares']     -= sell_qty
                    holdings[code]['total_cost'] -= avg * sell_qty
                    if holdings[code]['shares'] < 0.001:
                        holdings[code]['shares']     = 0
                        holdings[code]['total_cost'] = 0

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

        for zp in Position.query.filter_by(entity=ent).filter(Position.shares <= 0).all():
            db.session.delete(zp)

    db.session.commit()


def _fetch_yahoo_avg_price(code: str) -> dict:
    """
    Fetch 興櫃 official weighted average price (均價) directly from TPEX's
    market-info service (mis.tpex.org.tw) — the same source Yahoo Finance
    and 證券櫃買中心 website both use for 興櫃 均價.

    Endpoint: POST https://mis.tpex.org.tw/Quote.asmx/GETQ20
    Body: SymbolID=<code>
    Response: XML with <TradeStatisticAverage> = official 均價
    """
    import re as _re
    code_clean = code.strip().upper()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Referer': 'https://mis.tpex.org.tw/ib120stk.aspx',
    }

    try:
        url = 'https://mis.tpex.org.tw/Quote.asmx/GETQ20'
        resp = requests.post(url, data={'SymbolID': code_clean}, headers=headers, timeout=10)
        if resp.status_code == 200:
            xml = resp.text
            avg_match  = _re.search(r'<TradeStatisticAverage>([\d\.]+)</TradeStatisticAverage>', xml)
            name_match = _re.search(r'<SymbolName>([^<]+)</SymbolName>', xml)
            if avg_match:
                avg_price = float(avg_match.group(1))
                name = name_match.group(1) if name_match else ''
                if avg_price > 0:
                    return {'code': code, 'name': name, 'price': avg_price, 'date': date.today()}
    except Exception:
        pass

    # Fallback: Yahoo intraday VWAP if TPEX/mis endpoint fails
    for suffix in ['.TWO', '.TW']:
        try:
            url  = f'https://query1.finance.yahoo.com/v8/finance/chart/{code_clean}{suffix}'
            resp = requests.get(url, params={'interval': '1m', 'range': '1d'},
                                headers=headers, timeout=10)
            if resp.status_code != 200:
                continue
            result = resp.json().get('chart', {}).get('result', [])
            if not result:
                continue
            meta      = result[0].get('meta', {})
            name_val  = meta.get('longName') or meta.get('shortName') or ''
            indicators = result[0].get('indicators', {})
            closes    = indicators.get('quote', [{}])[0].get('close', [])
            volumes   = indicators.get('quote', [{}])[0].get('volume', [])
            total_val = sum(c * v for c, v in zip(closes, volumes) if c and v)
            total_vol = sum(v for c, v in zip(closes, volumes) if c and v)
            if total_val > 0 and total_vol > 0:
                vwap = round(total_val / total_vol, 2)
                return {'code': code, 'name': name_val, 'price': vwap, 'date': date.today()}
            price = meta.get('regularMarketPrice') or meta.get('previousClose')
            if price:
                return {'code': code, 'name': name_val, 'price': float(price), 'date': date.today()}
        except Exception:
            continue

    return {'code': code, 'name': '', 'price': None, 'date': None}


def fetch_twse_price(code: str, price_type: str = '成交價') -> dict:
    """
    Fetch price via Yahoo Finance (成交價) or TPEX (均價 for 興櫃).
    price_type: '成交價' (default) or '均價' (興櫃 weighted average)
    """
    if price_type == '均價':
        result = _fetch_yahoo_avg_price(code)
        if result['price']:
            return result
        # Fallback to Yahoo if TPEX fails

    code_clean = code.strip().upper()
    for suffix in ['.TW', '.TWO']:
        try:
            url     = f'https://query1.finance.yahoo.com/v8/finance/chart/{code_clean}{suffix}'
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            resp    = requests.get(url, params={'interval':'1d','range':'5d'},
                                   headers=headers, timeout=8)
            if resp.status_code != 200:
                continue
            result = resp.json().get('chart', {}).get('result', [])
            if not result:
                continue
            meta  = result[0].get('meta', {})
            price = meta.get('regularMarketPrice') or meta.get('previousClose')
            name  = meta.get('longName') or meta.get('shortName') or ''
            if price:
                return {'code': code, 'name': name, 'price': float(price), 'date': date.today()}
        except Exception:
            continue
    return {'code': code, 'name': '', 'price': None, 'date': None}


def fetch_twse_name(code: str) -> str:
    return fetch_twse_price(code).get('name', '')


def update_all_prices():
    codes   = [r[0] for r in db.session.query(Position.security_code)
               .filter(Position.shares > 0).distinct().all()]
    results = []
    for code in codes:
        sec    = Security.query.get(code)
        ptype  = (sec.price_type or '成交價') if sec else '成交價'
        fetch  = fetch_twse_price(code, price_type=ptype)
        old_px = None
        for pos in Position.query.filter_by(security_code=code).all():
            old_px = pos.last_price
            if fetch['price']:
                pos.last_price = fetch['price']
                pos.price_date = fetch['date']
        if sec and fetch['name'] and sec.name == code:
            sec.name = fetch['name']
        results.append({
            'code': code, 'name': sec.name if sec else code,
            'old_price': old_px, 'new_price': fetch['price'],
            'status': 'updated' if fetch['price'] else 'failed',
        })
    db.session.commit()
    return results


def calculate_realized_pnl(entity: str = None):
    """
    Calculate realized P&L for each entity by replaying transaction history.
    Returns dict: {entity: realized_pnl}
    """
    from .models import Transaction, ACCOUNT_MAP
    entities = [entity] if entity else list({v['entity'] for v in ACCOUNT_MAP.values()})
    result = {}

    for ent in entities:
        txns = (Transaction.query
                .filter_by(entity=ent)
                .filter(Transaction.security_code.isnot(None))
                .order_by(Transaction.trade_date)
                .all())

        holdings = {}
        realized = 0.0

        for t in txns:
            code = t.security_code
            if code not in holdings:
                holdings[code] = {'shares': 0.0, 'total_cost': 0.0}
            if t.shares > 0:
                holdings[code]['shares']     += t.shares
                holdings[code]['total_cost'] += t.gross_amount + t.fee
            else:
                if holdings[code]['shares'] > 0:
                    sell_qty   = abs(t.shares)
                    avg_cost   = holdings[code]['total_cost'] / holdings[code]['shares']
                    cost_basis = avg_cost * sell_qty
                    realized  += t.net_amount - cost_basis
                    holdings[code]['shares']     -= sell_qty
                    holdings[code]['total_cost'] -= avg_cost * sell_qty
                    if holdings[code]['shares'] < 0.001:
                        holdings[code]['shares']     = 0
                        holdings[code]['total_cost'] = 0

        result[ent] = round(realized, 0)

    return result
