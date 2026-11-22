// Aside CDP에 실제로 붙을 수 있는지 확인 (run_daily.ps1이 씀). 붙으면 0, 아니면 1
const { chromium } = require('playwright');
const t = setTimeout(() => process.exit(1), 20000);
chromium.connectOverCDP(process.env.ASIDE_CDP || 'http://127.0.0.1:9222', { timeout: 15000 })
  .then(() => { clearTimeout(t); console.log('CDP OK'); process.exit(0); })
  .catch(() => process.exit(1));
