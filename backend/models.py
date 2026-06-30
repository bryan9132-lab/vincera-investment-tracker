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

# ── Foreign (海外) investment entities — completely separate ledger from
# the Taiwan entities above. Same broker (國泰世華銀行) but Sophie/RC keep
# the records fully separate, so these never touch TW Position/cash logic. ──
FOREIGN_ENTITIES = ['私RC', '私華強']           # Phase 1: private-bank US/JP holdings
FOREIGN_CURRENCIES = ['USD', 'JPY']             # currency-segregated, like Sophie's sheets
FOREIGN_REGIONS = {'USD': '美國', 'JPY': '日本'}  # for display labeling

# ── Cash account master config ─────────────────────────────────────────────
# is_static=True  → balance is a single number, no ledger entries
# is_static=False → full ledger with CashEntry rows
CASH_ACCOUNTS = [
    # ── RC ──
    {
        'id': 'rc_dunnan',       'entity': 'RC',   'name': '國泰世華敦南（個人）',
        'category': '非投資',    'bank': '國泰世華',
        'opening_balance': 1385581, 'is_static': False,
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
    """Stock/security master — code, name, region, price_type"""
    __tablename__ = 'securities'

    code        = db.Column(db.String(20),  primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    region      = db.Column(db.String(10),  default='T')
    price_type  = db.Column(db.String(10),  default='成交價')  # '成交價' or '均價' (興櫃)
    currency    = db.Column(db.String(5),   default='TWD')    # 'TWD' / 'USD' / 'JPY' — for foreign securities
    created_at  = db.Column(db.DateTime,    default=datetime.utcnow)

    def to_dict(self):
        return {'code': self.code, 'name': self.name, 'region': self.region,
                'price_type': self.price_type or '成交價', 'currency': self.currency or 'TWD'}


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


class AuditLog(db.Model):
    """
    Tracks every delete/edit action Sophie takes.
    Stores a snapshot of the original data so it can be recovered.
    """
    __tablename__ = 'audit_logs'

    id          = db.Column(db.Integer,     primary_key=True)
    action      = db.Column(db.String(20),  nullable=False)   # 'delete' / 'edit'
    table_name  = db.Column(db.String(40),  nullable=False)   # 'transactions' / 'cash_entries' / 'fund_entries'
    record_id   = db.Column(db.Integer,     nullable=False)   # original PK
    summary     = db.Column(db.String(300), nullable=True)    # human-readable description
    snapshot    = db.Column(db.Text,        nullable=True)    # JSON snapshot of original record
    created_at  = db.Column(db.DateTime,    default=datetime.utcnow)

    def to_dict(self):
        return {
            'id':         self.id,
            'action':     self.action,
            'table_name': self.table_name,
            'record_id':  self.record_id,
            'summary':    self.summary,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M'),
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


# ══════════════════════════════════════════════════════════════════════════════
# Foreign (海外) investment models — 私RC / 私華強 (Phase 1)
#
# Deliberately separate tables from Transaction/Position (not just a new
# `entity` value) because: (1) currency is core to every row here and would
# otherwise be a TWD-only field bolted on, (2) keeps TW recalculate logic
# completely untouched as confirmed with Bryan, (3) JP security codes are
# 4-digit numbers that can collide with TW codes, so foreign JP securities
# are keyed as '<code>.JP' (matching the 地區 column convention Sophie
# already uses in 證券名稱JPY) to avoid clashing with Security.code for TW.
# USD tickers are stored as-is (alpha tickers don't collide with TW numeric
# codes).
# ══════════════════════════════════════════════════════════════════════════════

class ForeignTransaction(db.Model):
    """One row per foreign (US/JP) trade — manual entry or PDF parse, for 私RC/私華強."""
    __tablename__ = 'foreign_transactions'

    id              = db.Column(db.Integer,     primary_key=True)
    trade_date      = db.Column(db.Date,        nullable=False)
    settle_date     = db.Column(db.Date,        nullable=True)
    entity          = db.Column(db.String(20),  nullable=False)   # '私RC' / '私華強'
    currency        = db.Column(db.String(5),   nullable=False)   # 'USD' / 'JPY'
    security_code   = db.Column(db.String(20),  db.ForeignKey('securities.code'), nullable=True)
    security_name   = db.Column(db.String(100), nullable=True)
    shares          = db.Column(db.Float,       nullable=False)   # +buy / -sell
    price           = db.Column(db.Float,       nullable=True)    # 投資單價
    gross_amount    = db.Column(db.Float,       nullable=False)   # 成交價金
    fee             = db.Column(db.Float,       default=0)
    tax             = db.Column(db.Float,       default=0)        # 證交稅 (USD sheet only)
    net_amount      = db.Column(db.Float,       nullable=False)   # 應收付金額
    memo            = db.Column(db.String(200), nullable=True)
    source_file     = db.Column(db.String(200), nullable=True)
    created_at      = db.Column(db.DateTime,    default=datetime.utcnow)

    security        = db.relationship('Security', backref='foreign_transactions')

    def to_dict(self):
        return {
            'id':            self.id,
            'trade_date':    self.trade_date.isoformat(),
            'settle_date':   self.settle_date.isoformat() if self.settle_date else None,
            'entity':        self.entity,
            'currency':      self.currency,
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


class ForeignPosition(db.Model):
    """Current foreign holdings per entity per currency per security (私RC/私華強)."""
    __tablename__ = 'foreign_positions'

    id              = db.Column(db.Integer,     primary_key=True)
    entity          = db.Column(db.String(20),  nullable=False)
    currency        = db.Column(db.String(5),   nullable=False)
    security_code   = db.Column(db.String(20),  db.ForeignKey('securities.code'), nullable=False)
    shares          = db.Column(db.Float,       default=0)
    total_cost      = db.Column(db.Float,       default=0)        # in native currency
    avg_cost        = db.Column(db.Float,       default=0)
    last_price      = db.Column(db.Float,       nullable=True)
    price_date      = db.Column(db.Date,        nullable=True)
    updated_at      = db.Column(db.DateTime,    default=datetime.utcnow, onupdate=datetime.utcnow)

    security        = db.relationship('Security', backref='foreign_positions')

    __table_args__ = (
        db.UniqueConstraint('entity', 'currency', 'security_code', name='uq_foreign_entity_currency_security'),
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
            'currency':       self.currency,
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


class ForeignUploadLog(db.Model):
    """Track uploaded foreign PDFs to prevent duplicates (mirrors UploadLog)."""
    __tablename__ = 'foreign_upload_logs'

    id              = db.Column(db.Integer,     primary_key=True)
    filename        = db.Column(db.String(200), nullable=False)
    entity          = db.Column(db.String(20),  nullable=False)
    currency        = db.Column(db.String(5),   nullable=False)
    trade_date      = db.Column(db.Date,        nullable=False)
    status          = db.Column(db.String(20),  default='pending')
    uploaded_at     = db.Column(db.DateTime,    default=datetime.utcnow)
    confirmed_at    = db.Column(db.DateTime,    nullable=True)

    __table_args__ = (
        db.UniqueConstraint('entity', 'currency', 'trade_date', 'filename', name='uq_foreign_account_date_file'),
    )


class FxRate(db.Model):
    """
    Daily FX rate snapshot for display conversion (USD→TWD, JPY→TWD).
    Separate tab in the UI per Bryan's request, so foreign tables stay
    in native currency without crowding the layout.
    """
    __tablename__ = 'fx_rates'

    id          = db.Column(db.Integer,    primary_key=True)
    currency    = db.Column(db.String(5),  nullable=False)   # 'USD' / 'JPY'
    rate_date   = db.Column(db.Date,       nullable=False)   # date this rate applies to
    rate        = db.Column(db.Float,      nullable=False)   # 1 unit of currency = rate TWD
    source      = db.Column(db.String(20), default='manual') # 'manual' or 'auto'
    created_at  = db.Column(db.DateTime,   default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('currency', 'rate_date', name='uq_currency_rate_date'),
    )

    def to_dict(self):
        return {
            'id': self.id, 'currency': self.currency,
            'rate_date': self.rate_date.isoformat(), 'rate': self.rate,
            'source': self.source,
        }




DIVIDEND_BROKERS = ['元大', '統一', '私銀國泰']
DIVIDEND_ENTITIES = ['RC', '華強']


class CashDividend(db.Model):
    """現金股利 — cash dividend record, manually entered by Sophie."""
    __tablename__ = 'cash_dividends'

    id                    = db.Column(db.Integer,     primary_key=True)
    announce_date         = db.Column(db.Date,        nullable=False)   # 日期 (除息日/announcement)
    entity                = db.Column(db.String(20),  nullable=False)   # RC or 華強
    broker                = db.Column(db.String(20),  nullable=False)   # 元大/統一/私銀國泰
    security_code         = db.Column(db.String(20),  db.ForeignKey('securities.code'), nullable=False)
    shares_held           = db.Column(db.Float,       nullable=False)   # 股數 at time of entry (auto-filled, editable)
    dividend_per_share    = db.Column(db.Float,       nullable=False)   # 每股配發
    total_amount          = db.Column(db.Float,       nullable=False)   # 總額 = shares_held * dividend_per_share
    period_note           = db.Column(db.String(50),  nullable=True)    # 所屬期間 (free text, e.g. '2025/Q4')
    expected_deposit_date = db.Column(db.Date,        nullable=True)    # 預計入帳日期
    deposited             = db.Column(db.Boolean,      default=False)   # Sophie manually marks True once cash is moved to 資金細項
    deposited_at          = db.Column(db.DateTime,     nullable=True)
    cash_entry_id         = db.Column(db.Integer,      db.ForeignKey('cash_entries.id'), nullable=True)  # linked ledger entry once deposited
    created_at            = db.Column(db.DateTime,     default=datetime.utcnow)

    security              = db.relationship('Security', backref='cash_dividends')

    def to_dict(self):
        return {
            'id':                    self.id,
            'announce_date':         self.announce_date.isoformat() if self.announce_date else None,
            'entity':                self.entity,
            'broker':                self.broker,
            'security_code':         self.security_code,
            'security_name':         self.security.name if self.security else self.security_code,
            'shares_held':           self.shares_held,
            'dividend_per_share':    self.dividend_per_share,
            'total_amount':          self.total_amount,
            'period_note':           self.period_note,
            'expected_deposit_date': self.expected_deposit_date.isoformat() if self.expected_deposit_date else None,
            'deposited':             self.deposited,
            'deposited_at':          self.deposited_at.isoformat() if self.deposited_at else None,
            'cash_entry_id':         self.cash_entry_id,
        }


class StockDividend(db.Model):
    """股票股利 — stock dividend record, manually entered by Sophie."""
    __tablename__ = 'stock_dividends'

    id                     = db.Column(db.Integer,     primary_key=True)
    announce_date          = db.Column(db.Date,        nullable=False)  # 日期 (除權日)
    entity                 = db.Column(db.String(20),  nullable=False)
    broker                 = db.Column(db.String(20),  nullable=False)
    security_code          = db.Column(db.String(20),  db.ForeignKey('securities.code'), nullable=False)
    shares_held            = db.Column(db.Float,       nullable=False)  # 庫存股數 at time of entry (auto-filled, editable)
    dividend_ratio         = db.Column(db.Float,        nullable=False) # 每股配發 (e.g. 0.3 = 0.3 bonus shares per share)
    bonus_shares           = db.Column(db.Float,        nullable=False) # 股票股利總數 = shares_held * dividend_ratio
    period_note            = db.Column(db.String(50),   nullable=True)
    expected_allocate_date = db.Column(db.Date,         nullable=True)  # 預計撥券日期
    allocated              = db.Column(db.Boolean,       default=False) # Sophie manually confirms shares landed (集保)
    allocated_at           = db.Column(db.DateTime,      nullable=True)
    transaction_id         = db.Column(db.Integer,       db.ForeignKey('transactions.id'), nullable=True)  # linked synthetic Transaction once allocated
    created_at             = db.Column(db.DateTime,      default=datetime.utcnow)

    security               = db.relationship('Security', backref='stock_dividends')

    def to_dict(self):
        return {
            'id':                     self.id,
            'announce_date':          self.announce_date.isoformat() if self.announce_date else None,
            'entity':                 self.entity,
            'broker':                 self.broker,
            'security_code':          self.security_code,
            'security_name':          self.security.name if self.security else self.security_code,
            'shares_held':            self.shares_held,
            'dividend_ratio':         self.dividend_ratio,
            'bonus_shares':           self.bonus_shares,
            'period_note':            self.period_note,
            'expected_allocate_date': self.expected_allocate_date.isoformat() if self.expected_allocate_date else None,
            'allocated':              self.allocated,
            'allocated_at':           self.allocated_at.isoformat() if self.allocated_at else None,
            'transaction_id':         self.transaction_id,
        }
