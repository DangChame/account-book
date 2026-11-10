// 네이버페이 내역 수집 도구
//   node naver.js login   : 일회용 번호 로그인. ~/.config/ledger/naver_code 파일에 번호가 생기면 입력.
//   node naver.js history : 저장된 세션으로 페이머니 내역 페이지를 열어 텍스트/응답 저장.
// 세션(쿠키)은 ~/.config/ledger/naver_state.json (권한 600, 저장소 밖)에만 저장한다.
const { chromium } = require('playwright');
const fs = require('fs');
const os = require('os');
const path = require('path');

const DIR = path.join(os.homedir(), '.config', 'ledger');
const STATE = path.join(DIR, 'naver_state.json');
const CODE = path.join(DIR, 'naver_code');
const OUT = process.env.NAVER_OUT || path.join(DIR, 'naver_out');
const HISTORY = 'https://pay.naver.com/paymoney/history';
const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36';

function saveState(state) {
  fs.mkdirSync(DIR, { recursive: true });
  fs.writeFileSync(STATE, JSON.stringify(state), { mode: 0o600 });
}

async function login() {
  fs.mkdirSync(DIR, { recursive: true });
  try { fs.unlinkSync(CODE); } catch {}
  const b = await chromium.launch();
  const ctx = await b.newContext({ locale: 'ko-KR', timezoneId: 'Asia/Seoul', userAgent: UA, viewport: { width: 1280, height: 900 } });
  const p = await ctx.newPage();
  await p.goto('https://nid.naver.com/nidlogin.login?url=' + encodeURIComponent(HISTORY), { waitUntil: 'load' });
  await p.click('#onetime_login');
  await p.waitForSelector('#OnetimeCode');
  console.log('READY', new Date().toISOString());
  const deadline = Date.now() + 15 * 60 * 1000;
  while (!fs.existsSync(CODE)) {
    if (Date.now() > deadline) { console.log('TIMEOUT'); await b.close(); process.exit(1); }
    await new Promise(r => setTimeout(r, 1000));
  }
  const code = fs.readFileSync(CODE, 'utf8').trim();
  fs.unlinkSync(CODE);
  await p.fill('#OnetimeCode', code);
  await p.click('[id="otnlog.login"]');
  await p.waitForTimeout(6000);
  console.log('AFTER', p.url());
  fs.writeFileSync(path.join(DIR, 'naver_after.txt'), (await p.innerText('body')).slice(0, 2000));
  const cookies = await ctx.cookies();
  const ok = cookies.some(c => c.name === 'NID_SES');
  if (ok) { saveState(await ctx.storageState()); console.log('LOGIN OK'); }
  else console.log('LOGIN FAIL');
  await b.close();
}

async function history() {
  if (!fs.existsSync(STATE)) { console.log('NO SESSION'); process.exit(2); }
  fs.mkdirSync(OUT, { recursive: true });
  const b = await chromium.launch();
  const ctx = await b.newContext({ locale: 'ko-KR', timezoneId: 'Asia/Seoul', userAgent: UA, storageState: STATE, viewport: { width: 1280, height: 1600 } });
  const p = await ctx.newPage();
  const apis = [];
  p.on('response', async r => {
    const ct = r.headers()['content-type'] || '';
    if (ct.includes('json') && /pay\.naver\.com/.test(r.url())) {
      try { apis.push({ url: r.url(), body: await r.json() }); } catch {}
    }
  });
  await p.goto(HISTORY, { waitUntil: 'load' });
  await p.waitForTimeout(6000);
  console.log('URL', p.url());
  if (/nidlogin/.test(p.url())) { console.log('SESSION EXPIRED'); await b.close(); process.exit(3); }
  fs.writeFileSync(path.join(OUT, 'page.txt'), await p.innerText('body'));
  fs.writeFileSync(path.join(OUT, 'api.json'), JSON.stringify(apis, null, 1), { mode: 0o600 });
  saveState(await ctx.storageState());
  console.log('SAVED', apis.length, 'api responses');
  await b.close();
}

async function points() {
  // node naver.js points 20261101 20261130  -> naver_out/points.json (적립/사용 내역)
  if (!fs.existsSync(STATE)) { console.log('NO SESSION'); process.exit(2); }
  const [from, to] = process.argv.slice(3);
  fs.mkdirSync(OUT, { recursive: true });
  const b = await chromium.launch();
  const ctx = await b.newContext({ locale: 'ko-KR', timezoneId: 'Asia/Seoul', userAgent: UA, storageState: STATE });
  const p = await ctx.newPage();
  await p.goto('https://point.pay.naver.com/pointshistory/list?category=all', { waitUntil: 'load' });
  if (/nidlogin/.test(p.url())) { console.log('SESSION EXPIRED'); await b.close(); process.exit(3); }
  const trades = [];
  let body = { categoryType: 'ALL', tradeDateRange: { from, to } };
  for (let i = 0; i < 20; i++) {
    const j = await p.evaluate(async (bd) => {
      const r = await fetch('/pd/api/point-history/accumulable-list', { method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(bd) });
      return r.json();
    }, body);
    trades.push(...(j.trades || []));
    const cur = j.pageableCursor || {};
    if (!cur.next) break;
    body = { ...body, pageableCursor: { next: cur.next, nextTradeId: cur.nextTradeId } };
  }
  fs.writeFileSync(path.join(OUT, 'points.json'), JSON.stringify(trades, null, 1), { mode: 0o600 });
  saveState(await ctx.storageState());
  console.log('POINTS', trades.length);
  await b.close();
}

async function kbmail() {
  // node naver.js kbmail ['[농협카드 화면]' nhmail] -> naver_out/<name>.json
  // 지정한 제목(기본 '[국민카드 문자]')의 메일만 읽는다 (다른 메일은 열지 않음)
  if (!fs.existsSync(STATE)) { console.log('NO SESSION'); process.exit(2); }
  const KW = process.argv[3] || '[국민카드 문자]';
  const NAME = process.argv[4] || 'kbmail';
  fs.mkdirSync(OUT, { recursive: true });
  const b = await chromium.launch();
  const ctx = await b.newContext({ locale: 'ko-KR', timezoneId: 'Asia/Seoul', userAgent: UA, storageState: STATE });
  const p = await ctx.newPage();
  await p.goto('https://mail.naver.com/v2/folders/0/all', { waitUntil: 'load', timeout: 45000 });
  if (/nidlogin/.test(p.url())) { console.log('SESSION EXPIRED'); await b.close(); process.exit(3); }
  const mails = await p.evaluate(async (kw) => {
    const out = [];
    for (let page = 1; page <= 5; page++) {
      const r = await fetch('/json/search/?page=' + page + '&folderSN=-1&subject=' + encodeURIComponent(kw), { method: 'POST', credentials: 'include' });
      const j = await r.json();
      const hits = (j.mailData || []).filter(m => (m.subject || '').includes(kw));
      for (const m of hits) {
        const x = await fetch('/json/read/?mailSN=' + m.mailSN + '&markRead=false', { method: 'POST', credentials: 'include' });
        const d = await x.json(); const mi = d.mailInfo || {};
        out.push({ mailSN: m.mailSN, time: m.receivedTime || m.sentTime,
                   body: (mi.body || '').replace(/<br\s*\/?>/gi, '\n').replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').trim() });
      }
      if (page >= (j.lastPage || 1)) break;
    }
    return out;
  }, KW);
  fs.writeFileSync(path.join(OUT, NAME + '.json'), JSON.stringify(mails, null, 1), { mode: 0o600 });
  saveState(await ctx.storageState());
  console.log(NAME.toUpperCase(), mails.length);
  await b.close();
}

async function payhist() {
  // node naver.js payhist [pages=2] -> naver_out/payhist.json : 네이버페이 결제내역(상품명, 금액, 결제수단)
  if (!fs.existsSync(STATE)) { console.log('NO SESSION'); process.exit(2); }
  const pages = parseInt(process.argv[3] || '2', 10);
  fs.mkdirSync(OUT, { recursive: true });
  const b = await chromium.launch();
  const ctx = await b.newContext({ locale: 'ko-KR', timezoneId: 'Asia/Seoul', userAgent: UA, storageState: STATE });
  const p = await ctx.newPage();
  const items = [];
  for (let i = 1; i <= pages; i++) {
    await p.goto('https://pay.naver.com/pc/history?page=' + i, { waitUntil: 'load', timeout: 45000 });
    if (/nidlogin/.test(p.url())) { console.log('SESSION EXPIRED'); await b.close(); process.exit(3); }
    const nd = JSON.parse(await p.evaluate(() => document.getElementById('__NEXT_DATA__').textContent));
    const q = nd.props.pageProps.dehydratedState.queries.find(x => x.queryKey[0] === 'PAYMENT_LIST');
    for (const it of (q ? q.state.data.pages[0].items : [])) {
      const a = it.additionalData || {};
      items.push({ id: it._id, date: it.date, merchant: it.merchantName, product: (it.product || {}).name,
        price: (it.product || {}).price, rest: (it.product || {}).restAmount, status: (it.status || {}).text,
        method: a.paymentMethod, orderAmount: a.orderAmount, service: it.serviceType });
    }
  }
  fs.writeFileSync(path.join(OUT, 'payhist.json'), JSON.stringify(items, null, 1), { mode: 0o600 });
  saveState(await ctx.storageState());
  console.log('PAYHIST', items.length);
  await b.close();
}

({ login, history, points, kbmail, payhist })[process.argv[2]]().catch(e => { console.error(e); process.exit(1); });
