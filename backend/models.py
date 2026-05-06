"""
Database models for Sophie Investment Tracker
Using SQLite via SQLAlchemy for simplicity — easy to migrate to PostgreSQL later
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# ── Account → Entity mapping (config, not a DB table) ──────────────────────
ACCOUNT_MAP = {
    '600826': {'entity': 'RC',       'broker': '統一'},
    '133376': {'entity': 'RC',       'broker': '元大'},
    '600885': {'entity': '華強',      'broker': '統一'},
    '133311': {'entity': '華強',      'broker': '元大'},
    '006439': {'entity': '私銀RC',    'broker': '國泰'},
    '007065': {'entity': '私銀華強',  'broker': '國泰'},
}

ENTITIES = ['RC', '華強', '私銀RC', '私銀華強']


class Security(db.Model):
    """Stock/security master — code, name, region"""
    __tablename__ = 'securities'

    code        = db.Column(db.String(20),  primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    region      = db.Column(db.String(10),  default='T')   # T=Taiwan, U=US, etc.
    created_at  = db.Column(db.DateTime,    default=datetime.utcnow)

    def to_dict(self):
        return {'code': self.code, 'name': self.name, 'region': self.region}


class Transaction(db.Model):
    """
    One row per trade line from a broker PDF.
    Negative shares = sell, positive = buy.
    """
    __tablename__ = 'transactions'

    id              = db.Column(db.Integer,     primary_key=True)
    trade_date      = db.Column(db.Date,        nullable=False)
    settle_date     = db.Column(db.Date,        nullable=True)
    entity          = db.Column(db.String(20),  nullable=False)   # RC / 華強 / 私銀RC / 私銀華強
    broker          = db.Column(db.String(20),  nullable=False)   # 統一 / 元大 / 國泰
    account_no      = db.Column(db.String(20),  nullable=False)
    security_code   = db.Column(db.String(20),  db.ForeignKey('securities.code'), nullable=True)
    security_name   = db.Column(db.String(100), nullable=True)    # fallback if code unknown
    shares          = db.Column(db.Float,       nullable=False)   # negative = sell
    price           = db.Column(db.Float,       nullable=False)
    gross_amount    = db.Column(db.Float,       nullable=False)   # shares * price (always positive)
    fee             = db.Column(db.Float,       default=0)
    tax             = db.Column(db.Float,       default=0)
    net_amount      = db.Column(db.Float,       nullable=False)   # what actually moves
    memo            = db.Column(db.String(200), nullable=True)    # e.g. 資金調撥
    source_file     = db.Column(db.String(200), nullable=True)    # original PDF filename
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
    """
    Current holdings per entity per security.
    Recalculated whenever transactions are added.
    """
    __tablename__ = 'positions'

    id              = db.Column(db.Integer,     primary_key=True)
    entity          = db.Column(db.String(20),  nullable=False)
    security_code   = db.Column(db.String(20),  db.ForeignKey('securities.code'), nullable=False)
    shares          = db.Column(db.Float,       default=0)        # total shares held
    total_cost      = db.Column(db.Float,       default=0)        # cumulative investment cost
    avg_cost        = db.Column(db.Float,       default=0)        # per share
    last_price      = db.Column(db.Float,       nullable=True)    # latest market price
    price_date      = db.Column(db.Date,        nullable=True)    # when price was last updated
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
            'entity':        self.entity,
            'security_code': self.security_code,
            'security_name': self.security.name if self.security else self.security_code,
            'shares':        self.shares,
            'total_cost':    self.total_cost,
            'avg_cost':      round(self.avg_cost, 4),
            'last_price':    self.last_price,
            'price_date':    self.price_date.isoformat() if self.price_date else None,
            'market_value':  self.market_value(),
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
    status          = db.Column(db.String(20),  default='pending')  # pending/confirmed/rejected
    uploaded_at     = db.Column(db.DateTime,    default=datetime.utcnow)
    confirmed_at    = db.Column(db.DateTime,    nullable=True)

    __table_args__ = (
        db.UniqueConstraint('account_no', 'trade_date', name='uq_account_date'),
    )
