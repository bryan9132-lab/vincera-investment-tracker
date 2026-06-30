"""
Business logic:
  - Recalculate positions from transaction history
  - Fetch live prices via Yahoo Finance (works globally)
"""

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from datetime import date, datetime, timedelta
from .models import db, Transaction, Position, Security, ACCOUNT_MAP, CashDividend


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
        # mis.tpex.org.tw's cert fails strict verification (missing Subject Key
        # Identifier) even though browsers accept it — disable verification
        # for this specific public, non-sensitive read-only endpoint.
        resp = requests.post(url, data={'SymbolID': code_clean}, headers=headers,
                             timeout=10, verify=False)
        print(f'[均價] GETQ20 {code_clean} status={resp.status_code} body_len={len(resp.text)}', flush=True)
        if resp.status_code == 200:
            xml = resp.text
            avg_match  = _re.search(r'<TradeStatisticAverage>([\d\.]+)</TradeStatisticAverage>', xml)
            name_match = _re.search(r'<SymbolName>([^<]+)</SymbolName>', xml)
            print(f'[均價] avg_match={avg_match.group(1) if avg_match else None}', flush=True)
            if avg_match:
                avg_price = float(avg_match.group(1))
                name = name_match.group(1) if name_match else ''
                if avg_price > 0:
                    print(f'[均價] SUCCESS {code_clean} = {avg_price}', flush=True)
                    return {'code': code, 'name': name, 'price': avg_price, 'date': date.today()}
        else:
            print(f'[均價] non-200 response body: {resp.text[:200]}', flush=True)
    except Exception as ex:
        print(f'[均價] EXCEPTION for {code_clean}: {type(ex).__name__}: {ex}', flush=True)

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


def get_realized_pnl_ledger(entity: str = None, broker: str = None, category: str = None):
    """
    Build the full audit trail behind 已實現損益 — every event that
    contributes to realized P&L, with enough detail (avg cost, cost basis)
    for Sophie to see exactly where each number came from.

    Read-only by design: every row here is derived from other tabs
    (交易記錄 for 股票賣出, 股利管理 for 現金股利). Nothing is editable here.

    category: '股票買賣' | '貨幣基金' | '現金股利' | None (all)
    NOTE: 貨幣基金獲利/利息 isn't modeled as its own entry type in VIT yet
    (CASH_ENTRY_TYPES has no '基金獲利' type), so that category returns
    an empty list for now until we decide how Sophie should record it.
    """
    from .models import ACCOUNT_MAP
    rows = []

    # ── 股票買賣 (weighted-average-cost replay, same method as calculate_realized_pnl) ──
    if category in (None, '', '股票買賣'):
        entities = [entity] if entity else list({v['entity'] for v in ACCOUNT_MAP.values()})
        for ent in entities:
            q = (Transaction.query
                 .filter_by(entity=ent)
                 .filter(Transaction.security_code.isnot(None))
                 .order_by(Transaction.trade_date, Transaction.id))
            if broker:
                q = q.filter_by(broker=broker)
            txns = q.all()

            holdings = {}  # code -> {shares, total_cost}
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
                        realized   = t.net_amount - cost_basis
                        rows.append({
                            'date':            t.trade_date.isoformat() if t.trade_date else None,
                            'entity':          ent,
                            'broker':          t.broker,
                            'category':        '股票買賣',
                            'security_code':   code,
                            'security_name':   t.security_name or code,
                            'shares':          sell_qty,
                            'price':           t.price,
                            'gross_amount':    t.gross_amount,
                            'fee':             t.fee,
                            'tax':             t.tax,
                            'net_amount':      t.net_amount,
                            'avg_cost':        round(avg_cost, 4),
                            'cost_basis':      round(cost_basis, 0),
                            'realized_pnl':    round(realized, 0),
                            'note':            None,
                        })
                        holdings[code]['shares']     -= sell_qty
                        holdings[code]['total_cost'] -= avg_cost * sell_qty
                        if holdings[code]['shares'] < 0.001:
                            holdings[code]['shares']     = 0
                            holdings[code]['total_cost'] = 0

    # ── 現金股利 (counted on announce_date, regardless of deposit/maturity date) ──
    if category in (None, '', '現金股利'):
        q = CashDividend.query
        if entity:
            q = q.filter_by(entity=entity)
        if broker:
            q = q.filter_by(broker=broker)
        for cd in q.order_by(CashDividend.announce_date).all():
            rows.append({
                'date':            cd.announce_date.isoformat() if cd.announce_date else None,
                'entity':          cd.entity,
                'broker':          cd.broker,
                'category':        '現金股利',
                'security_code':   cd.security_code,
                'security_name':   cd.security.name if cd.security else cd.security_code,
                'shares':          cd.shares_held,
                'price':           cd.dividend_per_share,
                'gross_amount':    cd.total_amount,
                'fee':             None,
                'tax':             None,
                'net_amount':      cd.total_amount,
                'avg_cost':        None,
                'cost_basis':      None,
                'realized_pnl':    cd.total_amount,
                'note':            '待入帳' if not cd.deposited else None,
            })

    # ── 貨幣基金 (申購/贖回利息) — not yet modeled as its own entry type ──
    # Placeholder: returns nothing for this category until a dedicated
    # CASH_ENTRY_TYPES entry (e.g. '基金獲利') exists to source this from.

    rows.sort(key=lambda r: r['date'] or '')
    return rows


# ══════════════════════════════════════════════════════════════════════════════
# Foreign (海外) investment logic — 私RC / 私華強 (Phase 1)
#
# Mirrors recalculate_positions / calculate_realized_pnl but scoped to
# ForeignTransaction/ForeignPosition, segregated by (entity, currency).
# Uses round(..., 6) during replay (not raw float subtraction) to avoid the
# 1.8e-12 floating-point residue seen in Sophie's 證券名稱USD sheet.
# ══════════════════════════════════════════════════════════════════════════════

def recalculate_foreign_positions(entity: str = None, currency: str = None):
    from .models import ForeignTransaction, ForeignPosition, FOREIGN_ENTITIES, FOREIGN_CURRENCIES

    entities   = [entity] if entity else FOREIGN_ENTITIES
    currencies = [currency] if currency else FOREIGN_CURRENCIES

    for ent in entities:
        for cur in currencies:
            txns = (ForeignTransaction.query
                    .filter_by(entity=ent, currency=cur)
                    .filter(ForeignTransaction.security_code.isnot(None))
                    .filter(ForeignTransaction.shares != 0)
                    .order_by(ForeignTransaction.trade_date, ForeignTransaction.id)
                    .all())

            holdings = {}
            for txn in txns:
                code = txn.security_code
                if code not in holdings:
                    holdings[code] = {'shares': 0.0, 'total_cost': 0.0}
                if txn.shares > 0:
                    holdings[code]['shares']     = round(holdings[code]['shares'] + txn.shares, 6)
                    holdings[code]['total_cost'] = round(holdings[code]['total_cost'] + txn.gross_amount + txn.fee, 6)
                else:
                    if holdings[code]['shares'] > 0:
                        sell_qty = abs(txn.shares)
                        avg      = holdings[code]['total_cost'] / holdings[code]['shares']
                        holdings[code]['shares']     = round(holdings[code]['shares'] - sell_qty, 6)
                        holdings[code]['total_cost'] = round(holdings[code]['total_cost'] - avg * sell_qty, 6)
                        if holdings[code]['shares'] < 0.001:
                            holdings[code]['shares']     = 0
                            holdings[code]['total_cost'] = 0

            for code, data in holdings.items():
                shares = data['shares']
                cost   = data['total_cost']
                # Clean up floating-point residue (e.g. -1.8e-12) instead of
                # carrying it forward like the old Excel did.
                if abs(shares) < 1e-6:
                    shares = 0
                if abs(cost) < 1e-6:
                    cost = 0
                pos = ForeignPosition.query.filter_by(entity=ent, currency=cur, security_code=code).first()
                if pos is None:
                    pos = ForeignPosition(entity=ent, currency=cur, security_code=code)
                    db.session.add(pos)
                pos.shares     = round(shares, 4)
                pos.total_cost = round(cost, 4)
                pos.avg_cost   = round(cost / shares, 4) if shares > 0 else 0

            for zp in (ForeignPosition.query.filter_by(entity=ent, currency=cur)
                       .filter(ForeignPosition.shares <= 0).all()):
                db.session.delete(zp)

    db.session.commit()


def calculate_foreign_realized_pnl(entity: str = None, currency: str = None):
    """Returns dict: {(entity, currency): realized_pnl}"""
    from .models import ForeignTransaction, FOREIGN_ENTITIES, FOREIGN_CURRENCIES

    entities   = [entity] if entity else FOREIGN_ENTITIES
    currencies = [currency] if currency else FOREIGN_CURRENCIES
    result = {}

    for ent in entities:
        for cur in currencies:
            txns = (ForeignTransaction.query
                    .filter_by(entity=ent, currency=cur)
                    .filter(ForeignTransaction.security_code.isnot(None))
                    .order_by(ForeignTransaction.trade_date, ForeignTransaction.id)
                    .all())

            holdings = {}
            realized = 0.0
            for t in txns:
                code = t.security_code
                if code not in holdings:
                    holdings[code] = {'shares': 0.0, 'total_cost': 0.0}
                if t.shares > 0:
                    holdings[code]['shares']     = round(holdings[code]['shares'] + t.shares, 6)
                    holdings[code]['total_cost'] = round(holdings[code]['total_cost'] + t.gross_amount + t.fee, 6)
                else:
                    if holdings[code]['shares'] > 0:
                        sell_qty   = abs(t.shares)
                        avg_cost   = holdings[code]['total_cost'] / holdings[code]['shares']
                        cost_basis = avg_cost * sell_qty
                        realized  += t.net_amount - cost_basis
                        holdings[code]['shares']     = round(holdings[code]['shares'] - sell_qty, 6)
                        holdings[code]['total_cost'] = round(holdings[code]['total_cost'] - avg_cost * sell_qty, 6)
                        if holdings[code]['shares'] < 0.001:
                            holdings[code]['shares']     = 0
                            holdings[code]['total_cost'] = 0

            result[(ent, cur)] = round(realized, 0)

    return result


def get_latest_fx_rate(currency: str):
    """Latest manually-entered or auto-fetched FX rate (1 unit currency = N TWD)."""
    from .models import FxRate
    row = (FxRate.query.filter_by(currency=currency)
           .order_by(FxRate.rate_date.desc()).first())
    return row.rate if row else None
