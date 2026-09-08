import { bpath, api, fmtTime, elapsed } from './common.js?v=5';

const $ = (s) => document.querySelector(s);
const LS = 'goiso.counter.' + ((window.__BRANCH__) || '');
let state = { counter_id: null, staff_name: '' };
let view = null;
let timer = null;
let poll = null;

/* -------------------------------------------------- đồng hồ */
setInterval(() => $('#clock').textContent = new Date().toLocaleTimeString('vi-VN', { hour12: false }), 1000);

/* -------------------------------------------------- khôi phục phiên */
try {
  const saved = JSON.parse(localStorage.getItem(LS) || 'null');
  if (saved && saved.counter_id) { state = saved; enterConsole(); }
} catch (_) {}

/* -------------------------------------------------- đăng nhập */
$('#btn-login').addEventListener('click', async () => {
  const cid = $('#sel-counter').value;
  const staff = $('#inp-staff').value.trim();
  const pin = $('#inp-pin') ? $('#inp-pin').value.trim() : '';
  if (!staff) { showSetupErr('Nhập tên cán bộ.'); return; }
  try {
    await api(bpath(`/counter/${encodeURIComponent(cid)}/login`), { method: 'POST', body: { staff_name: staff, pin } });
    state = { counter_id: cid, staff_name: staff };
    localStorage.setItem(LS, JSON.stringify(state));
    enterConsole();
  } catch (e) { showSetupErr(e.message); }
});

$('#btn-switch').addEventListener('click', async () => {
  if (state.counter_id && confirm('Kết thúc ca tại quầy này?')) {
    try { await api(bpath(`/counter/${encodeURIComponent(state.counter_id)}/status`), { method: 'POST', body: { status: 'offline' } }); } catch (_) {}
  }
  localStorage.removeItem(LS);
  location.reload();
});

function showSetupErr(m) { const el = $('#setup-err'); el.textContent = m; el.classList.remove('hidden'); }
function showErr(m) { const el = $('#err'); el.textContent = m; el.classList.remove('hidden'); setTimeout(() => el.classList.add('hidden'), 4000); }

function backToSetup(msg) {
  localStorage.removeItem(LS);
  clearInterval(poll);
  $('#console').classList.add('hidden');
  $('#setup').classList.remove('hidden');
  if (msg) showSetupErr(msg);
}

function enterConsole() {
  $('#setup').classList.add('hidden');
  $('#console').classList.remove('hidden');
  $('#console').classList.add('grid');
  $('#lbl-counter').textContent = state.counter_id.replace(/\D/g, '') || state.counter_id;
  $('#lbl-staff').textContent = state.staff_name;
  if ($('#sel-counter')) $('#sel-counter').value = state.counter_id;
  refresh();
  clearInterval(poll);
  poll = setInterval(() => { if (!document.hidden) refresh(); }, 3000);
}

/* -------------------------------------------------- hành động */
const post = (action, body) =>
  api(bpath(`/counter/${encodeURIComponent(state.counter_id)}/${action}`),
      { method: 'POST', body: { staff_name: state.staff_name, ...body } });

$('#btn-next').addEventListener('click', () => act(() => post('next')));
$('#btn-recall').addEventListener('click', () => act(() => post('recall')));
$('#btn-done').addEventListener('click', () => act(() => post('done')));
$('#btn-missed').addEventListener('click', () => act(() => post('missed')));
$('#btn-pause').addEventListener('click', () => {
  const paused = view && view.status === 'paused';
  act(() => post('status', { status: paused ? 'active' : 'paused' }));
});
$('#frm-specific').addEventListener('submit', (e) => {
  e.preventDefault();
  const v = $('#inp-specific').value.trim();
  if (v) act(() => post('call', { full_no: v }).then(() => $('#inp-specific').value = ''));
});

window.addEventListener('keydown', (e) => {
  if ($('#console').classList.contains('hidden')) return;
  if (e.target.tagName === 'INPUT') return;
  if (e.code === 'Space') { e.preventDefault(); $('#btn-next').click(); }
  if (e.key.toLowerCase() === 'r') $('#btn-recall').click();
  if (e.key.toLowerCase() === 'd') $('#btn-done').click();
});

let busy = false;
async function act(fn) {
  if (busy) return;
  busy = true;
  document.querySelectorAll('#console button').forEach(b => b.disabled = true);
  try { const v = await fn(); if (v && Array.isArray(v.waiting)) applyView(v); else await refresh(); }
  catch (e) {
    if (/PIN|đăng nhập|Vào ca/i.test(e.message)) { backToSetup('Phiên quầy đã hết hạn, vui lòng Vào ca lại.'); return; }
    showErr(e.message);
  }
  finally {
    busy = false;
    document.querySelectorAll('#console button').forEach(b => b.disabled = false);
    updatePauseBtn();
  }
}

/* -------------------------------------------------- render */
async function refresh() {
  if (!state.counter_id) return;
  try {
    applyView(await api(bpath(`/counter/${encodeURIComponent(state.counter_id)}/view`)));
    $('#conn').classList.add('hidden');
  }
  catch (e) { $('#conn').classList.remove('hidden'); }
}

function applyView(v) {
  view = v;
  const c = v.current;
  $('#cur-num').textContent = c ? c.full_no : '—';
  $('#cur-num').style.color = c ? c.service_color : '#94a3b8';
  $('#cur-svc').textContent = c ? c.service_short : '';
  $('#cur-name').textContent = c && c.fullname ? c.fullname : '';
  $('#stat-wait').textContent = v.waiting_count;
  $('#stat-done').textContent = v.done_today;

  $('#waitlist').innerHTML = v.waiting.map((w, i) => `
    <div class="flex items-center gap-2 rounded-lg px-3 py-2 ${i === 0 ? 'bg-gov-50 border border-gov/30' : 'bg-slate-50'}">
      <span class="font-mono font-bold tnum text-lg">${w.full_no}</span>
      ${w.source === 'online' ? '<span class="text-[10px] bg-emerald-100 text-emerald-700 rounded px-1.5 py-0.5 font-semibold">HẸN</span>' : ''}
      ${w.fullname ? `<span class="text-slate-500 text-sm truncate">${w.fullname}</span>` : ''}
      <span class="ml-auto text-xs text-slate-400">${fmtTime(w.time_issue)}</span>
    </div>`).join('') || '<div class="text-slate-400 text-sm">Không còn số chờ.</div>';

  $('#history').innerHTML = v.history.map(h => {
    const tag = h.status === 'done' ? '<span class="text-emerald-600">xong</span>'
      : h.status === 'missed' ? '<span class="text-amber-600">vắng</span>'
      : '<span class="text-gov">đang gọi</span>';
    return `<div class="flex justify-between"><span class="font-mono tnum">${h.full_no}</span>${tag}<span class="text-slate-400">${fmtTime(h.time_start)}</span></div>`;
  }).join('') || '<div class="text-slate-400">—</div>';

  updatePauseBtn();
  clearInterval(timer);
  if (c) {
    const upd = () => $('#cur-time').textContent = elapsed(c.since);
    upd(); timer = setInterval(upd, 1000);
  } else {
    $('#cur-time').textContent = '0:00';
  }
}

function updatePauseBtn() {
  const b = $('#btn-pause');
  if (view && view.status === 'paused') { b.textContent = '▶ Tiếp tục'; b.classList.add('bg-amber-100'); }
  else { b.textContent = '⏸ Tạm dừng'; b.classList.remove('bg-amber-100'); }
}
