"""
Database models for Vincera Investment Tracker (VIT)
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# ── Investment account → entity/broker mapping ─────────────────────────────
ACCOUNT_MAP = {
    '600826': {'entity': 'RC',       'broker': '統一'},
    '133376': {'entity': 'RC',       'broker': '元大'},
    '600885': {'entity': '華強',      'broker': '統一'},
    '133311': {'entity': '華強',      'broker': '元大'},
    '006439': {'entity': '私銀RC',    'broker': '國泰'},
    '007065': {'entity': '私銀華強',  'broker': '國泰'},
}

ENTITIES = ['RC', '華強', '私銀RC', '私銀華強']

# ── Cash account master config ─────────────────────────────────────────────
# is_static=True  → balance is a single number, no ledger entries
# is_static=False → full ledger with CashEntry rows
CASH_ACCOUNTS = [
    # ── RC ──
    {
        'id': 'rc_dunnan',       'entity': 'RC',   'name': '國泰世華敦南（個人）',
        'category': '非投資',    'bank': '國泰世華',
        'opening_balance': 1765594, 'is_static': False,
    },
    {
        'id': 'rc_tuni',         'entity': 'RC',   'name': '國泰復興(統一)',
        'category': '股票投資',  'bank': '國泰世華',
        'opening_balance': 6097,    'is_static': False,
    },
    {
        'id': 'rc_yuanta',       'entity': 'RC',   'name': '國泰光復(元大)',
        'category': '股票投資',  'bank': '國泰世華',
        'opening_balance': 436546,  'is_static': False,
    },
    {
        'id': 'rc_private',      'entity': 'RC',   'name': '國泰世華世貿(私銀)',
        'category': '股票投資',  'bank': '國泰世華',
        'opening_balance': 1766363, 'is_static': False,
    },
    {
        'id': 'rc_fund',         'entity': 'RC',   'name': '貨幣基金(RC)',
        'category': '基金投資',  'bank': '國泰世華',
        'opening_balance': 0,       'is_static': False,
    },
    {
        'id': 'rc_other',        'entity': 'RC',   'name': '其他',
        'category': '非投資',    'bank': None,
        'opening_balance': 822,     'is_static': True,
    },
    # ── 華強 ──
    {
        'id': 'hq_tuni',         'entity': '華強',  'name': '國泰復興(統一)',
        'category': '股票投資',  'bank': '國泰世華',
        'opening_balance': 191796,  'is_static': False,
    },
    {
        'id': 'hq_yuanta',       'entity': '華強',  'name': '國泰南東(元大)',
        'category': '股票投資',  'bank': '國泰世華',
        'opening_balance': 134714,  'is_static': False,
    },
    {
        'id': 'hq_dunnan',       'entity': '華強',  'name': '國泰世華敦南',
        'category': '非投資',    'bank': '國泰世華',
        'opening_balance': 314907,  'is_static': False,
    },
    {
        'id': 'hq_private',      'entity': '華強',  'name': '國泰世華世貿(私銀)',
        'category': '股票投資',  'bank': '國泰世華',
        'opening_balance': 6792016, 'is_static': False,
    },
    {
        'id': 'hq_fund',         'entity': '華強',  'name': '貨幣基金(華強)',
        'category': '基金投資',  'bank': '國泰世華',
        'opening_balance': 0,       'is_static': False,
    },
    {
        'id': 'hq_huanan',       'entity': '華強',  'name': '華南銀行敦和',
        'category': '非投資',    'bank': '華南銀行',
        'opening_balance': 612903,  'is_static': False,
    },
    {
        'id': 'hq_fubon',        'entity': '華強',  'name': '富邦建國',
        'category': '非投資',    'bank': '富邦',
        'opening_balance': 7061,    'is_static': True,
    },
    {
        'id': 'hq_yuanta_bank',  'entity': '華強',  'name': '元大銀行營業部',
        'category': '非投資',    'bank': '元大銀行',
        'opening_balance': 39455,   'is_static': True,
    },
]

# Quick lookup: cash_account_id by entity
CASH_ACCOUNTS_BY_ID = {a['id']: a for a in CASH_ACCOUNTS}

# Map broker account_no → cash_account_id (for auto-update on trade confirm)
CASH_ACCOUNT_BROKER_MAP = {
    '600826': 'rc_tuni',        # RC統一
    '133376': 'rc_yuanta',      # RC元大
    '006439': 'rc_private',     # 私銀RC
    '600885': 'hq_tuni',        # 華強統一
    '133311': 'hq_yuanta',      # 華強元大
    '007065': 'hq_private',     # 私銀華強
}

# Fund accounts and their linked cash accounts
FUND_CASH_LINK = {
    'rc_fund':  'rc_private',   # 貨幣基金RC ↔ 私銀RC現金
    'hq_fund':  'hq_private',   # 貨幣基金華強 ↔ 私銀華強現金
}

# Cash entry transaction types
CASH_ENTRY_TYPES = [
    '買入股票',    # auto from trade confirm (investment accounts only)
    '賣出股票',    # auto from trade confirm (investment accounts only)
    '轉出賬戶',    # intra-entity transfer (RC↔RC or 華強↔華強 only)
    '申購基金',    # fund purchase (fund accounts only) → also debits private account
    '贖回基金',    # fund redemption (fund accounts only) → also credits private account
    '貸款',        # bank loan (私銀accounts only)
    '貸款還款',    # loan repayment (私銀accounts only)
    '借款',        # inter-entity loan (RC↔華強 only)
    '借款還款',    # inter-entity loan repayment (RC↔華強 only)
    '其他收入',    # manual misc credit
    '其他支出',    # manual misc debit
]


# ══════════════════════════════════════════════════════════════════════════════
# Existing models (unchanged)
# ══════════════════════════════════════════════════════════════════════════════

class Security(db.Model):
    """Stock/security master — code, name, region"""
    __tablename__ = 'securities'

    code        = db.Column(db.String(20),  primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    region      = db.Column(db.String(10),  default='T')
    created_at  = db.Column(db.DateTime,    default=datetime.utcnow)

    def to_dict(self):
        return {'code': self.code, 'name': self.name, 'region': self.region}


class Transaction(db.Model):
    """One row per trade line from a broker PDF."""
    __tablename__ = 'transactions'

    id              = db.Column(db.Integer,     primary_key=True)
    trade_date      = db.Column(db.Date,        nullable=False)
    settle_date     = db.Column(db.Date,        nullable=True)
    entity          = db.Column(db.String(20),  nullable=False)
    broker          = db.Column(db.String(20),  nullable=False)
    account_no      = db.Column(db.String(20),  nullable=False)
    security_code   = db.Column(db.String(20),  db.ForeignKey('securities.code'), nullable=True)
    security_name   = db.Column(db.String(100), nullable=True)
    shares          = db.Column(db.Float,       nullable=False)
    price           = db.Column(db.Float,       nullable=False)
    gross_amount    = db.Column(db.Float,       nullable=False)
    fee             = db.Column(db.Float,       default=0)
    tax             = db.Column(db.Float,       default=0)
    net_amount      = db.Column(db.Float,       nullable=False)
    memo            = db.Column(db.String(200), nullable=True)
    source_file     = db.Column(db.String(200), nullable=True)
    created_at      = db.Column(db.DateTime,    default=datetime.utcnow)

    security        = db.relationship('Security', backref='transactions')

    def to_dict(self):
        return {
            'id':            self.id,
            'trade_date':    self.trade_date.isoformat(),
            'settle_date':   self.settle_date.isoformat() if self.settle_date else None,
            'entity':        self.entity,
            'broker':        self.broker,
            'account_no':    self.account_no,
            'security_code': self.security_code,
            'security_name': self.security_name,
            'shares':        self.shares,
            'price':         self.price,
            'gross_amount':  self.gross_amount,
            'fee':           self.fee,
            'tax':           self.tax,
            'net_amount':    self.net_amount,
            'memo':          self.memo,
        }


class Position(db.Model):
    """Current holdings per entity per security."""
    __tablename__ = 'positions'

    id              = db.Column(db.Integer,     primary_key=True)
    entity          = db.Column(db.String(20),  nullable=False)
    security_code   = db.Column(db.String(20),  db.ForeignKey('securities.code'), nullable=False)
    shares          = db.Column(db.Float,       default=0)
    total_cost      = db.Column(db.Float,       default=0)
    avg_cost        = db.Column(db.Float,       default=0)
    last_price      = db.Column(db.Float,       nullable=True)
    price_date      = db.Column(db.Date,        nullable=True)
    updated_at      = db.Column(db.DateTime,    default=datetime.utcnow, onupdate=datetime.utcnow)

    security        = db.relationship('Security', backref='positions')

    __table_args__ = (
        db.UniqueConstraint('entity', 'security_code', name='uq_entity_security'),
    )

    def market_value(self):
        if self.last_price:
            return self.shares * self.last_price
        return None

    def unrealized_pnl(self):
        mv = self.market_value()
        if mv is not None:
            return mv - self.total_cost
        return None

    def to_dict(self):
        return {
            'entity':         self.entity,
            'security_code':  self.security_code,
            'security_name':  self.security.name if self.security else self.security_code,
            'shares':         self.shares,
            'total_cost':     self.total_cost,
            'avg_cost':       round(self.avg_cost, 4),
            'last_price':     self.last_price,
            'price_date':     self.price_date.isoformat() if self.price_date else None,
            'market_value':   self.market_value(),
            'unrealized_pnl': self.unrealized_pnl(),
        }


class UploadLog(db.Model):
    """Track uploaded PDFs to prevent duplicates"""
    __tablename__ = 'upload_logs'

    id              = db.Column(db.Integer,     primary_key=True)
    filename        = db.Column(db.String(200), nullable=False)
    account_no      = db.Column(db.String(20),  nullable=False)
    trade_date      = db.Column(db.Date,        nullable=False)
    broker          = db.Column(db.String(20),  nullable=False)
    status          = db.Column(db.String(20),  default='pending')
    uploaded_at     = db.Column(db.DateTime,    default=datetime.utcnow)
    confirmed_at    = db.Column(db.DateTime,    nullable=True)

    __table_args__ = (
        db.UniqueConstraint('account_no', 'trade_date', name='uq_account_date'),
    )


# ══════════════════════════════════════════════════════════════════════════════
# New models — Cash tracking
# ══════════════════════════════════════════════════════════════════════════════

class CashAccount(db.Model):
    """
    Master record for each cash account.
    Static accounts (is_static=True) have no CashEntry rows —
    balance is stored directly on this model.
    """
    __tablename__ = 'cash_accounts'

    id              = db.Column(db.String(30),  primary_key=True)   # e.g. 'rc_tuni'
    entity          = db.Column(db.String(20),  nullable=False)     # RC / 華強
    name            = db.Column(db.String(60),  nullable=False)
    category        = db.Column(db.String(20),  nullable=False)     # 股票投資 / 非投資 / 基金投資
    bank            = db.Column(db.String(30),  nullable=True)
    opening_balance = db.Column(db.Float,       default=0)
    balance         = db.Column(db.Float,       default=0)          # current balance (kept in sync)
    is_static       = db.Column(db.Boolean,     default=False)      # True = no ledger, manual balance only
    sort_order      = db.Column(db.Integer,     default=0)
    updated_at      = db.Column(db.DateTime,    default=datetime.utcnow, onupdate=datetime.utcnow)

    entries         = db.relationship('CashEntry', backref='account',
                                      foreign_keys='CashEntry.account_id',
                                      order_by='CashEntry.entry_date, CashEntry.id')

    def to_dict(self):
        return {
            'id':               self.id,
            'entity':           self.entity,
            'name':             self.name,
            'category':         self.category,
            'bank':             self.bank,
            'opening_balance':  self.opening_balance,
            'balance':          self.balance,
            'is_static':        self.is_static,
        }


class CashEntry(db.Model):
    """
    One row per cash movement in a non-static account.

    For linked transfers (轉出賬戶, 借款, etc.), both sides of the transfer
    share the same linked_entry_id so they can be displayed/deleted together.

    For fund transactions (申購/贖回基金), the fund ledger row and the
    corresponding private-account cash row share the same linked_entry_id.
    """
    __tablename__ = 'cash_entries'

    id              = db.Column(db.Integer,     primary_key=True)
    account_id      = db.Column(db.String(30),  db.ForeignKey('cash_accounts.id'), nullable=False)
    entry_date      = db.Column(db.Date,        nullable=False)
    entry_type      = db.Column(db.String(20),  nullable=False)     # from CASH_ENTRY_TYPES
    description     = db.Column(db.String(200), nullable=True)      # 交易內容 / 股票名稱 / memo
    amount          = db.Column(db.Float,       nullable=False)     # positive=流入, negative=流出
    balance_after   = db.Column(db.Float,       nullable=False)     # running balance after this entry

    # For fund entries only
    security_code   = db.Column(db.String(20),  nullable=True)      # stock code if trade-linked
    security_name   = db.Column(db.String(100), nullable=True)

    # Links two entries that are two sides of one operation
    # (transfer out + transfer in, fund purchase + cash debit, etc.)
    linked_entry_id = db.Column(db.Integer,     db.ForeignKey('cash_entries.id'), nullable=True)

    # Back-reference to the Transaction that triggered this entry (auto entries)
    transaction_id  = db.Column(db.Integer,     db.ForeignKey('transactions.id'), nullable=True)

    is_auto         = db.Column(db.Boolean,     default=False)      # True = created by trade confirm
    created_at      = db.Column(db.DateTime,    default=datetime.utcnow)

    transaction     = db.relationship('Transaction', backref='cash_entries')

    def to_dict(self):
        return {
            'id':               self.id,
            'account_id':       self.account_id,
            'entry_date':       self.entry_date.isoformat(),
            'entry_type':       self.entry_type,
            'description':      self.description,
            'amount':           self.amount,
            'balance_after':    self.balance_after,
            'security_code':    self.security_code,
            'security_name':    self.security_name,
            'linked_entry_id':  self.linked_entry_id,
            'transaction_id':   self.transaction_id,
            'is_auto':          self.is_auto,
        }


class FundEntry(db.Model):
    """
    One row per 貨幣基金 transaction (申購 or 贖回).
    Mirrors the Excel 貨幣基金(RC/華強) sheet columns A–I.
    """
    __tablename__ = 'fund_entries'

    id                  = db.Column(db.Integer,  primary_key=True)
    account_id          = db.Column(db.String(30), db.ForeignKey('cash_accounts.id'), nullable=False)  # rc_fund / hq_fund
    entry_date          = db.Column(db.Date,     nullable=False)           # col A
    cost                = db.Column(db.Float,    nullable=False)           # col B 投資成本 (neg=sell cost)
    unit_cost           = db.Column(db.Float,    nullable=True)            # col C 單位成本
    units               = db.Column(db.Float,    nullable=False)           # col D 單位數 (neg=redemption)
    cumulative_amount   = db.Column(db.Float,    nullable=False)           # col E 累積金額
    cumulative_units    = db.Column(db.Float,    nullable=False)           # col F 累積股數
    avg_unit_cost       = db.Column(db.Float,    nullable=True)            # col G 平均單位成本
    redemption_amount   = db.Column(db.Float,    nullable=True)            # col H 賣出金額
    profit              = db.Column(db.Float,    nullable=True)            # col I 處分利益

    # Links to the CashEntry rows generated on the linked cash account
    linked_cash_entry_id = db.Column(db.Integer, db.ForeignKey('cash_entries.id'), nullable=True)
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)

    fund_account        = db.relationship('CashAccount', backref='fund_entries')

    def to_dict(self):
        return {
            'id':                   self.id,
            'account_id':           self.account_id,
            'entry_date':           self.entry_date.isoformat(),
            'cost':                 self.cost,
            'unit_cost':            self.unit_cost,
            'units':                self.units,
            'cumulative_amount':    self.cumulative_amount,
            'cumulative_units':     self.cumulative_units,
            'avg_unit_cost':        self.avg_unit_cost,
            'redemption_amount':    self.redemption_amount,
            'profit':               self.profit,
        }
