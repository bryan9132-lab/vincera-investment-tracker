"""
send_migration.py — Run once to migrate Excel data into VIT
Usage: python send_migration.py
"""
import base64, json, urllib.request, urllib.error

VIT_URL    = 'https://web-production-573485.up.railway.app/api/migrate'
SECRET     = 'vincera2026'
EXCEL_FILE = 'test-20260505.xlsx'

print(f'Reading {EXCEL_FILE}...')
with open(EXCEL_FILE, 'rb') as f:
    excel_b64 = base64.b64encode(f.read()).decode('utf-8')

print(f'Sending to VIT ({len(excel_b64)//1024} KB)...')
payload = json.dumps({'secret': SECRET, 'excel_data': excel_b64, 'force': True}).encode('utf-8')
req = urllib.request.Request(VIT_URL, data=payload, headers={'Content-Type':'application/json'}, method='POST')

try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode('utf-8'))
        print('\n✅ Migration successful!')
        print(f'   Total transactions: {result["total_transactions"]}')
        print('\n   Per sheet:')
        for sheet, count in result['summary'].items():
            print(f'   {sheet}: {count}')
except urllib.error.HTTPError as e:
    print(f'❌ Error {e.code}: {e.read().decode("utf-8")}')
except Exception as e:
    print(f'❌ Failed: {e}')
