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

async function loginpw() {
  // NAVER_CRED 파일(1줄: 아이디, 2줄: 비밀번호)로 '로그인 상태 유지' 켜고 로그인. 자격 파일은 읽은 즉시 삭제.
  const credPath = process.env.NAVER_CRED;
  const [id, pw] = fs.readFileSync(credPath, 'utf8').split(/\r?\n/).map(s => s.trim());
  const b = await chromium.launch();
  const ctx = await b.newContext({ locale: 'ko-KR', timezoneId: 'Asia/Seoul', userAgent: UA, viewport: { width: 1280, height: 900 } });
  const p = await ctx.newPage();
  await p.goto('https://nid.naver.com/nidlogin.login?mode=form&url=' + encodeURIComponent(HISTORY), { waitUntil: 'load' });
  await p.click('#id'); await p.keyboard.type(id, { delay: 120 });
  await p.click('#pw'); await p.keyboard.type(pw, { delay: 130 });
  // '로그인 상태 유지' 켜기 (라벨 클릭 후 실제 체크 여부 확인)
  const stay = p.locator('input[name=nvlong]').first();
  for (let i = 0; i < 2 && !(await stay.isChecked().catch(() => false)); i++)
    await p.getByText('로그인 상태 유지', { exact: true }).first().click();
  // IP 보안 끄기 (IP가 바뀌어도 로그인 유지)
  const ip = p.locator('input[name=ipcheck]').first();
  if (await ip.isChecked().catch(() => false)) await p.getByText('IP 보안', { exact: true }).first().click().catch(() => {});
  console.log('keep', await stay.isChecked().catch(() => '?'), 'ipsec', await ip.isChecked().catch(() => '?'));
  await p.screenshot({ path: path.join(DIR, 'naver_before_login.png') });
  await p.getByRole('button', { name: '로그인', exact: true }).first().click();
  const deadline = Date.now() + 20 * 60 * 1000;
  while (Date.now() < deadline) {
    await p.waitForTimeout(3000);
    if ((await ctx.cookies()).some(c => c.name === 'NID_AUT')) break;
    const body = await p.innerText('body').catch(() => '');
    if (/자동입력 방지|보안문자|추가 확인|captcha/i.test(body)) {
      // 사람이 직접 푼다: 화면 저장 → 사용자 답(naver_captcha_answer 파일) 대기 → 입력
      const ans = path.join(DIR, 'naver_captcha_answer');
      try { fs.unlinkSync(ans); } catch {}
      // 영수증 이미지가 다 뜰 때까지 기다린 뒤 문제 영역만 찍어서 텔레그램으로 보낸다
      await p.waitForLoadState('networkidle').catch(() => {});
      await p.waitForFunction(() => [...document.images].filter(i => i.offsetParent).every(i => i.complete && i.naturalWidth > 0), null, { timeout: 15000 }).catch(() => {});
      await p.waitForTimeout(2000);
      await p.screenshot({ path: path.join(DIR, 'naver_captcha.png'), fullPage: true });
      require('child_process').spawnSync('python3', [path.join(__dirname, 'tg.py'), '--photo', path.join(DIR, 'naver_captcha.png'),
        '네이버 보안확인: 빈칸 정답을 Claude 대화창에 보내주세요 (15분)'], { stdio: 'inherit' });
      console.log('CAPTCHA', new Date().toISOString());
      const until = Date.now() + 15 * 60 * 1000;
      while (!fs.existsSync(ans) && Date.now() < until) await new Promise(r => setTimeout(r, 1000));
      if (!fs.existsSync(ans)) { console.log('CAPTCHA TIMEOUT'); break; }
      const a = fs.readFileSync(ans, 'utf8').trim(); fs.unlinkSync(ans);
      await p.getByPlaceholder('정답을 입력해 주세요').fill(a).catch(() => p.locator('input[type=text]').last().fill(a));
      if (await p.locator('input[name=pw], #pw').first().isVisible().catch(() => false)) {
        await p.locator('#pw').click(); await p.keyboard.type(pw, { delay: 130 });
      }
      await p.getByRole('button', { name: /확인|로그인/ }).first().click();
      console.log('CAPTCHA SUBMITTED');
      continue;
    }
    if (/비밀번호를 잘못|아이디 또는 비밀번호/.test(body)) { console.log('WRONG PW'); break; }
    if (/2단계|인증 요청|승인/.test(body)) console.log('WAITING 2FA');
    // 비밀번호가 비워진 로그인 폼으로 돌아오면 다시 입력
    if (await p.locator('#pw').isVisible().catch(() => false) && !(await p.locator('#pw').inputValue().catch(() => 'x'))) {
      await p.locator('#pw').click(); await p.keyboard.type(pw, { delay: 130 });
      await p.getByRole('button', { name: '로그인', exact: true }).first().click().catch(() => {});
      console.log('RETYPED PW');
    }
    await p.screenshot({ path: path.join(DIR, 'naver_status.png') }).catch(() => {});
    const head = body.split('\n').map(x => x.trim()).filter(Boolean).slice(0, 6).join(' / ');
    if (head !== globalThis.__lastHead) { console.log('PAGE', p.url().slice(0, 60), '|', head.slice(0, 160)); globalThis.__lastHead = head; }
  }
  const cookies = await ctx.cookies();
  console.log('URL', p.url().slice(0, 80));
  if (cookies.some(c => c.name === 'NID_AUT')) {
    const aut = cookies.find(c => c.name === 'NID_AUT');
    saveState(await ctx.storageState());
    console.log('LOGIN OK, NID_AUT expires', aut.expires > 0 ? new Date(aut.expires * 1000).toISOString() : 'session');
  } else {
    await p.screenshot({ path: path.join(DIR, 'naver_login_fail.png') });
    console.log('LOGIN FAIL');
  }
  try { fs.unlinkSync(credPath); } catch {}
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
        const x = await fetch('/json/read/?mailSN=' + m.mailSN + '&markRead=true', { method: 'POST', credentials: 'include' });
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
    const raw = await p.evaluate(() => { const e = document.getElementById('__NEXT_DATA__'); return e ? e.textContent : null; });
    if (!raw) { console.log('NO DATA page', i, p.url()); break; }
    const nd = JSON.parse(raw);
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

({ login, loginpw, history, points, kbmail, payhist })[process.argv[2]]().catch(e => { console.error(e); process.exit(1); });
