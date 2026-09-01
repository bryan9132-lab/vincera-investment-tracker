# VIT — Vincera Investment Tracker

> A full-stack portfolio management system built for a Taiwan family office, replacing manual Excel workflows with a live, multi-entity investment tracker.

[**Live Demo**](https://web-production-573485.up.railway.app/demo) · Built by [Bryan Chen](mailto:bryan.chen@berkeley.edu)

\---

## Background

Vincera Capital manages equity positions across **4 entities** (two principals, two private banking arms) and **3 brokers**, with a portfolio exceeding NT$140M. Before VIT, all trade reconciliation, P\&L tracking, and reporting were done manually in Excel — error-prone, time-consuming, and lacking any audit trail.

VIT centralises every investment workflow into a single web application, giving the operations team a real-time view of holdings, cash, and performance across all entities at once



!\[Holdings](screenshots/Holdings.png)

\---

## What It Does

### 📄 Trade Upload — Two Paths

Broker statement PDFs are dragged onto an upload zone and auto-parsed — ticker, shares, price, fee, tax, and net amount extracted and previewed before saving. Three broker formats (Sinopac, Mega, Cathay) each have a dedicated parser. For OTC trades or direct capital subscriptions, Sophie enters trades manually with auto-calculated fees and net amount validation.

### 📊 Real-Time Market Prices

One button fetches the latest closing price for every held security from the **Taiwan Stock Exchange (TWSE) public API**, instantly updating unrealized P\&L across all positions. Each security supports two price modes (transaction price vs. average price), toggled per stock without re-fetching.

### ⚖️ Position \& P\&L Engine

Every confirmed trade triggers a full replay of transaction history using the **weighted-average cost method**, recomputing cost basis, average cost per share, and realized P\&L. The Holdings view shows projected average cost when pending stock dividends exist — before the shares officially arrive.

### 🎁 Dividend Management

* **Cash dividends** — entered on announcement date, marked deposited once credited, flows into Realized P\&L automatically
* **Stock dividends** — pending until allocation date with an ⏳ badge and projected new average cost shown in Holdings; one click confirms and updates the position
* **Capital increases** — direct cash subscriptions to unlisted companies tracked from payment date through share delivery

### 💰 Cash Account Ledger

Tracks 12 cash accounts across 4 entities — brokerage, private banking, personal bank, and money market funds. Every trade auto-debits/credits the correct account. Manual entries supported: fund transfers, bank loans, inter-entity shareholder loans, repayments, and unlisted dividend income.

### 📈 Realized P\&L — Full Audit Trail

Every income event (stock sales, money market income, cash dividends) is logged with computed net proceeds, cost basis, and gain/loss — filterable by entity, broker, category, and month. Manual adjustments can be applied to any computed row, with the original system value preserved. Full CSV export in one click.



!\[RealizedP\&L](screenshots/realizedgains.png)

### 📤 Excel Export — Daily Report

Exports a formatted Excel report matching the family office's existing reporting template: today's trades summary, full position table, P\&L summary (realized + unrealized side-by-side), and cash balances including private banking loans and shareholder loans. Column widths, fonts, borders, and number formats are all programmatically specified.



!\[ExcelExport](screenshots/export.png)

\---

## Tech Stack

|Layer|Technology|
|-|-|
|Backend|Python · Flask · SQLAlchemy ORM|
|Database|PostgreSQL|
|Frontend|Vanilla JavaScript (no framework)|
|PDF Parsing|pdfplumber (custom parser per broker format)|
|Excel Export|openpyxl|
|Market Data|TWSE Public REST API|
|Deployment|Railway (auto-deploy from GitHub)|

\~4,500 lines of code across 6 core files.

\---

## Project Status

✅ Core system in production use  
✅ PDF parsing for 3 broker formats  
✅ Multi-entity P\&L tracking with manual adjustment support  
🚧 Foreign investment module — USD/JPY positions, FX rate tracking, multi-currency cost basis

\---

## About

Built by **Bryan Chen** (Haas MBA '28), previously EVP at Vincera Capital. Designed, architected, and developed solo over 4 months while managing the family office — then deployed into active daily use by the operations team.

[Live Demo](https://web-production-573485.up.railway.app/demo) · [LinkedIn](https://linkedin.com/in/bryan-chen-haas) · [Email](mailto:bryan.chen@berkeley.edu)

