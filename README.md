# Sophie Investment Tracker

A web app to automate daily investment transaction recording for Richard Chen's portfolio.

## Structure
- backend/     → Flask API, database models, business logic
- frontend/    → HTML/CSS/JS web interface
- parsers/     → PDF parsers per broker (統一, 國泰, 元大)
- tests/       → Test files

## Entities
- RC          → 元大 (133376) + 統一 (600826)
- 華強        → 元大 (133311) + 統一 (600885)
- 私銀RC      → 國泰 (006439)
- 私銀華強    → 國泰 (007065)
