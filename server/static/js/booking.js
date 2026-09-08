/* Trợ lý đặt lịch hẹn online (không phụ thuộc framework). */
const $ = (s) => document.querySelector(s);
const TKEY = window.__TURNSTILE_KEY__ || '';

let branches = [];
let sel = { branch: null, prefix: null, date: null, slot: null };
let tsWidgetId = null;

async function jget(url) {
  const r = await fetch(url);
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || ('Lỗi ' + r.status));
  return d;
}
async function jpost(url, body) {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || ('Lỗi ' + r.status));
  return d;
}
function showErr(m) { const e = $('#err'); e.textContent = m; e.classList.remove('hidden'); e.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
function clearErr() { $('#err').classList.add('hidden'); }
function show(id, on = true) { $(id).classList.toggle('hidden', !on); }
const pad = (n) => String(n).padStart(2, '0');

/* ---------- bước 1: chi nhánh ---------- */
(async function init() {
  try {
    branches = (await jget('/api/booking/branches')).branches;
  } catch (e) { showErr(e.message); return; }
  if (!branches.length) { showErr('Hiện chưa có chi nhánh nào mở đặt lịch online.'); return; }
  $('#sel-branch').innerHTML = '<option value="">— chọn chi nhánh —</option>' +
    branches.map(b => `<option value="${b.code}">${b.name}</option>`).join('');
  $('#sel-branch').addEventListener('change', onBranch);
})();

function onBranch() {
  sel = { branch: branches.find(b => b.code === $('#sel-branch').value) || null, prefix: null, date: null, slot: null };
  clearErr();
  ['#s-service', '#s-date', '#s-slot', '#s-form', '#s-done'].forEach(x => show(x, false));
  if (!sel.branch) { $('#branch-addr').textContent = ''; return; }
  $('#branch-addr').textContent = sel.branch.address || '';
  $('#svc-list').innerHTML = sel.branch.services.map(s =>
    `<button class="chip" data-p="${s.prefix}" aria-pressed="false">${s.short || s.name}</button>`).join('');
  $('#svc-list').querySelectorAll('.chip').forEach(c => c.addEventListener('click', () => onService(c)));
  show('#s-service', true);
}

/* ---------- bước 2: dịch vụ ---------- */
function onService(chip) {
  $('#svc-list').querySelectorAll('.chip').forEach(c => c.setAttribute('aria-pressed', c === chip));
  sel.prefix = chip.dataset.p; sel.date = null; sel.slot = null;
  ['#s-slot', '#s-form', '#s-done'].forEach(x => show(x, false));

  const days = sel.branch.open_days_ahead || 3;
  const now = new Date();
  const wd = ['CN', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7'];
  let html = '';
  for (let i = 0; i <= days; i++) {
    const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() + i);
    const iso = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    html += `<button class="chip" data-d="${iso}" aria-pressed="false">${i === 0 ? 'Hôm nay' : wd[d.getDay()] + ' ' + d.getDate() + '/' + (d.getMonth() + 1)}</button>`;
  }
  $('#date-list').innerHTML = html;
  $('#date-list').querySelectorAll('.chip').forEach(c => c.addEventListener('click', () => onDate(c)));
  show('#s-date', true);
}

/* ---------- bước 3: ngày ---------- */
async function onDate(chip) {
  $('#date-list').querySelectorAll('.chip').forEach(c => c.setAttribute('aria-pressed', c === chip));
  sel.date = chip.dataset.d; sel.slot = null;
  ['#s-form', '#s-done'].forEach(x => show(x, false));
  clearErr();
  let slots;
  try {
    slots = (await jget(`/api/booking/${sel.branch.code}/slots?date=${sel.date}&prefix=${sel.prefix}`)).slots;
  } catch (e) { showErr(e.message); return; }
  const list = $('#slot-list');
  list.innerHTML = slots.map(s =>
    `<button class="chip" data-s="${s.start}" aria-pressed="false" ${s.full ? 'disabled' : ''}>
       ${s.start}<span class="block text-[10px] font-normal">${s.full ? 'hết chỗ' : 'còn ' + s.remaining}</span>
     </button>`).join('');
  show('#slot-empty', slots.filter(s => !s.full).length === 0);
  list.querySelectorAll('.chip:not([disabled])').forEach(c => c.addEventListener('click', () => onSlot(c)));
  show('#s-slot', true);
}

/* ---------- bước 4: khung giờ -> form ---------- */
function onSlot(chip) {
  $('#slot-list').querySelectorAll('.chip').forEach(c => c.setAttribute('aria-pressed', c === chip));
  sel.slot = chip.dataset.s;
  show('#s-form', true);
  $('#s-form').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  if (TKEY && window.turnstile && tsWidgetId === null) {
    $('#ts-widget').dataset.sitekey = TKEY;
    tsWidgetId = window.turnstile.render('#ts-widget', { sitekey: TKEY });
  }
}

/* ---------- bước 5: gửi ---------- */
$('#btn-book').addEventListener('click', async () => {
  clearErr();
  const body = {
    prefix: sel.prefix, slot_date: sel.date, slot_start: sel.slot,
    citizen_name: $('#f-name').value, cccd: $('#f-cccd').value, phone: $('#f-phone').value,
    turnstile_token: (TKEY && window.turnstile) ? window.turnstile.getResponse(tsWidgetId ?? undefined) : '',
  };
  $('#btn-book').disabled = true;
  try {
    const r = await jpost(`/api/booking/${sel.branch.code}/book`, body);
    renderDone(r);
  } catch (e) {
    showErr(e.message);
    if (TKEY && window.turnstile) window.turnstile.reset(tsWidgetId ?? undefined);
  } finally { $('#btn-book').disabled = false; }
});

function renderDone(r) {
  ['#s-branch', '#s-service', '#s-date', '#s-slot', '#s-form'].forEach(x => show(x, false));
  $('#r-code').textContent = r.code;
  $('#r-meta').innerHTML = `${r.branch_name}<br>${r.service_short} · ${r.slot_date} lúc <b>${r.slot_start}–${r.slot_end}</b>`;
  const link = location.origin + '/lich-hen/' + r.token;
  $('#r-link').href = link;
  $('#r-qr').innerHTML = '';
  new QRCode($('#r-qr'), { text: link, width: 168, height: 168 });
  show('#s-done', true);
  $('#s-done').scrollIntoView({ behavior: 'smooth', block: 'center' });
}
$('#btn-again').addEventListener('click', () => location.reload());
