"""
Flask API — all routes Sophie's frontend will call
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from datetime import datetime, date
import tempfile

from backend.models import db, Transaction, Position, Security, UploadLog, ACCOUNT_MAP
from backend.logic  import recalculate_positions, update_all_prices, fetch_twse_name
from parsers.pdf_parsers import parse_pdf
from backend.exporter import generate_excel


def create_app():
    app = Flask(__name__, static_folder='../frontend', static_url_path='')
    CORS(app)

    # Config
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', 'sqlite:///sophie.db'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

    db.init_app(app)

    with app.app_context():
        db.create_all()
        _seed_securities()

    # ── Serve frontend ───────────────────────────────────────────────────────
    @app.route('/')
    def index():
        return app.send_static_file('index.html')

    # ── PDF Upload & Parse ───────────────────────────────────────────────────
    @app.route('/api/upload', methods=['POST'])
    def upload_pdf():
        """
        Step 1: Upload PDF, parse it, return preview for Sophie to confirm.
        Does NOT save to DB yet.
        """
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file       = request.files['file']
        pdf_bytes  = file.read()
        filename   = file.filename

        parsed = parse_pdf(pdf_bytes, filename)

        if parsed.broker == 'unknown' or not parsed.account_no:
            return jsonify({
                'error': 'Could not identify broker or account',
                'details': parsed.errors
            }), 422

        # Check account mapping
        mapping = ACCOUNT_MAP.get(parsed.account_no)
        if not mapping:
            return jsonify({
                'error': f'Unknown account number: {parsed.account_no}',
                'details': ['This account is not in our mapping. Please contact admin.']
            }), 422

        # Check for duplicate upload
        existing = UploadLog.query.filter_by(
            account_no = parsed.account_no,
            trade_date = parsed.trade_date,
        ).first()
        if existing and existing.status == 'confirmed':
            return jsonify({
                'error': 'Duplicate upload',
                'details': [f'Transactions for {parsed.account_no} on {parsed.trade_date} already confirmed.']
            }), 409

        # Enrich with known security names
        trades_preview = []
        unknown_codes  = []
        for t in parsed.trades:
            sec  = Security.query.get(t.security_code)
            name = sec.name if sec else fetch_twse_name(t.security_code)
            if not name:
                unknown_codes.append(t.security_code)
            trades_preview.append({
                'security_code': t.security_code,
                'security_name': name or f'[Unknown: {t.security_code}]',
                'name_confirmed': bool(name),
                'shares':        t.shares,
                'price':         t.price,
                'gross_amount':  t.gross_amount,
                'fee':           t.fee,
                'tax':           t.tax,
                'net_amount':    t.net_amount,
            })

        return jsonify({
            'account_no':    parsed.account_no,
            'entity':        mapping['entity'],
            'broker':        parsed.broker,
            'trade_date':    parsed.trade_date.isoformat(),
            'settle_date':   parsed.settle_date.isoformat() if parsed.settle_date else None,
            'trades':        trades_preview,
            'unknown_codes': unknown_codes,
            'warnings':      parsed.errors,
        })

    # ── Confirm parsed PDF ───────────────────────────────────────────────────
    @app.route('/api/confirm', methods=['POST'])
    def confirm_upload():
        """
        Step 2: Sophie reviews and confirms — save to DB.
        Accepts the same structure returned by /api/upload,
        with any name corrections applied.
        """
        data = request.json
        if not data:
            return jsonify({'error': 'No data'}), 400

        account_no  = data['account_no']
        trade_date  = date.fromisoformat(data['trade_date'])
        settle_date = date.fromisoformat(data['settle_date']) if data.get('settle_date') else None
        mapping     = ACCOUNT_MAP[account_no]
        trades      = data['trades']

        # Save/update securities
        for t in trades:
            code = t['security_code']
            name = t['security_name']
            if code and not code.startswith('[Unknown'):
                sec = Security.query.get(code)
                if sec is None:
                    sec = Security(code=code, name=name)
                    db.session.add(sec)
                elif not sec.name or sec.name != name:
                    sec.name = name

        # Save transactions
        for t in trades:
            txn = Transaction(
                trade_date     = trade_date,
                settle_date    = settle_date,
                entity         = mapping['entity'],
                broker         = mapping['broker'],
                account_no     = account_no,
                security_code  = t['security_code'] if not t['security_code'].startswith('[') else None,
                security_name  = t['security_name'],
                shares         = t['shares'],
                price          = t['price'],
                gross_amount   = t['gross_amount'],
                fee            = t['fee'],
                tax            = t['tax'],
                net_amount     = t['net_amount'],
                source_file    = data.get('filename', ''),
            )
            db.session.add(txn)

        # Log upload
        log = UploadLog.query.filter_by(
            account_no=account_no, trade_date=trade_date
        ).first()
        if log is None:
            log = UploadLog(
                filename   = data.get('filename', ''),
                account_no = account_no,
                trade_date = trade_date,
                broker     = mapping['broker'],
            )
            db.session.add(log)
        log.status       = 'confirmed'
        log.confirmed_at = datetime.utcnow()

        db.session.commit()

        # Recalculate positions for this entity
        recalculate_positions(mapping['entity'])

        return jsonify({'status': 'ok', 'message': f'Saved {len(trades)} transactions'})

    # ── Get current positions ────────────────────────────────────────────────
    @app.route('/api/positions', methods=['GET'])
    def get_positions():
        """Return all current positions grouped by entity"""
        positions = Position.query.filter(Position.shares > 0).all()
        result    = {}
        for pos in positions:
            ent = pos.entity
            if ent not in result:
                result[ent] = []
            result[ent].append(pos.to_dict())
        return jsonify(result)

    # ── Update market prices ─────────────────────────────────────────────────
    @app.route('/api/prices/update', methods=['POST'])
    def update_prices():
        """Fetch latest TWSE prices for all held securities"""
        results = update_all_prices()
        return jsonify({
            'updated': len([r for r in results if r['status'] == 'updated']),
            'failed':  len([r for r in results if r['status'] == 'failed']),
            'details': results,
        })

    # ── Export Excel ─────────────────────────────────────────────────────────
    @app.route('/api/export', methods=['GET'])
    def export_excel():
        """Generate and download the 庫存總表 Excel report"""
        filepath = generate_excel()
        return send_file(
            filepath,
            as_attachment=True,
            download_name=f'庫存總表_{date.today().strftime("%Y%m%d")}.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    # ── One-time migration endpoint ──────────────────────────────────────────
    @app.route('/api/migrate', methods=['POST'])
    def run_migration():
        """
        One-time endpoint to migrate data from uploaded Excel.
        Protected by a secret key.
        """
        secret = request.json.get('secret', '')
        if secret != os.environ.get('MIGRATE_SECRET', 'vincera2026'):
            return jsonify({'error': 'Unauthorized'}), 401

        try:
            import openpyxl, sys
            from io import BytesIO
            import base64

            excel_b64 = request.json.get('excel_data')
            if not excel_b64:
                return jsonify({'error': 'No excel_data provided'}), 400

            excel_bytes = base64.b64decode(excel_b64)
            wb = openpyxl.load_workbook(BytesIO(excel_bytes), data_only=True)

            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            from migrate_excel import (migrate_rc_tuni, migrate_rc_yuanta,
                                       migrate_hq_tuni, migrate_hq_yuanta,
                                       migrate_private_rc, migrate_private_hq)

            # Clear existing
            Transaction.query.delete()
            Position.query.delete()
            db.session.commit()

            sheet_handlers = [
                ('(RC)統一進出明細TWD',   migrate_rc_tuni),
                ('(RC)元大進出明細TWD',   migrate_rc_yuanta),
                ('(華強)統一進出明細TWD', migrate_hq_tuni),
                ('(華強)元大進出明細TWD', migrate_hq_yuanta),
                ('(私RC)TWD',            migrate_private_rc),
                ('(私強)進出明細TWD',     migrate_private_hq),
            ]

            total = 0
            summary = {}
            for sheet_name, handler in sheet_handlers:
                ws     = wb[sheet_name]
                trades = handler(ws, app)
                summary[sheet_name] = len(trades)
                for t in trades:
                    code = t['security_code']
                    if code and not Security.query.get(code):
                        db.session.add(Security(code=code, name=code))
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
                        source_file   = 'excel_migration',
                    )
                    db.session.add(txn)
                    total += 1

            db.session.commit()
            recalculate_positions()

            return jsonify({
                'status': 'ok',
                'total_transactions': total,
                'summary': summary,
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    # ── Transaction history ──────────────────────────────────────────────────
    @app.route('/api/transactions', methods=['GET'])
    def get_transactions():
        """Return recent transactions, optionally filtered"""
        entity     = request.args.get('entity')
        start_date = request.args.get('start')
        end_date   = request.args.get('end')
        limit      = int(request.args.get('limit', 100))

        q = Transaction.query.order_by(Transaction.trade_date.desc())
        if entity:
            q = q.filter_by(entity=entity)
        if start_date:
            q = q.filter(Transaction.trade_date >= date.fromisoformat(start_date))
        if end_date:
            q = q.filter(Transaction.trade_date <= date.fromisoformat(end_date))

        txns = q.limit(limit).all()
        return jsonify([t.to_dict() for t in txns])

    # ── Securities lookup ────────────────────────────────────────────────────
    @app.route('/api/securities/lookup', methods=['GET'])
    def lookup_security():
        """Look up a stock code — first local DB, then TWSE"""
        code = request.args.get('code', '').strip()
        if not code:
            return jsonify({'error': 'No code provided'}), 400

        sec = Security.query.get(code)
        if sec:
            return jsonify({'code': code, 'name': sec.name, 'source': 'local'})

        name = fetch_twse_name(code)
        if name:
            return jsonify({'code': code, 'name': name, 'source': 'twse'})

        return jsonify({'code': code, 'name': None, 'source': None}), 404

    return app


def _seed_securities():
    """Pre-populate known securities from the Excel data"""
    known = {
        '6682':  '華旭先進',
        '3006':  '晶豪科',
        '6488':  '環球晶',
        '00981A':'主動統一台股增長',
        '00910': '第一金太空衛星',
        '8828':  '厲玉暣.KY',
        '6949':  '沛爾生醫-創',
        '7717':  '萊德光電-KY',
        '4573':  '高明鐵',
        '2308':  '台達電',
        '1717':  '長興',
        '00955': '中信日本商社',
        '7769':  '鴻勁',
    }
    for code, name in known.items():
        if not Security.query.get(code):
            db.session.add(Security(code=code, name=name))
    db.session.commit()


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
