import { api } from './common.js';

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
let cfg = { services: {}, counters: {}, extra: {} };

const EXTRA_TEXT = {
  ten_co_quan: 'Tên cơ quan', ten_chi_nhanh: 'Tên chi nhánh', link_qr: 'Link QR trên phiếu',
  lock_message: 'Thông báo ngoài giờ', voice_template: 'Mẫu câu đọc ({so}, {quay})',
};
const EXTRA_BOOL = {
  lock_time_enabled: 'Khoá theo giờ', qr_enabled: 'In mã QR', allow_saturday: 'Cho phép Thứ Bảy', allow_sunday: 'Cho phép Chủ nhật',
};
const EXTRA_NUM = {
  voice_rate: 'Tốc độ đọc (0.5–1.5)', voice_repeat: 'Số lần đọc lặp', spotlight_seconds: 'Giữ spotlight (giây)', recent_count: 'Số lượt hiển thị gần đây',
};

/* -------------------------------------------------- đăng nhập */
$('#btn-login').addEventListener('click', login);
$('#inp-pw').addEventListener('keydown', (e) => { if (e.key === 'Enter') login(); });
async function login() {
  try {
    await api('/api/admin/login', { method: 'POST', body: { password: $('#inp-pw').value } });
    $('#login').classList.add('hidden');
    $('#panel').classList.remove('hidden');
    $('#btn-logout').classList.remove('hidden');
    await load();
  } catch (e) { const el = $('#login-err'); el.textContent = e.message; el.classList.remove('hidden'); }
}
$('#btn-logout').addEventListener('click', async () => { await api('/api/admin/logout', { method: 'POST' }); location.reload(); });

/* -------------------------------------------------- tabs */
$$('.tab').forEach(b => b.addEventListener('click', () => {
  $$('.tab').forEach(x => { x.classList.remove('bg-gov', 'text-white'); x.classList.add('bg-white', 'border'); });
  b.classList.add('bg-gov', 'text-white'); b.classList.remove('bg-white', 'border');
  $$('[data-panel]').forEach(p => p.classList.toggle('hidden', p.dataset.panel !== b.dataset.tab));
  if (b.dataset.tab === 'stats') loadStats();
}));

/* -------------------------------------------------- nạp cấu hình */
async function load() {
  cfg = await api('/api/admin/config');
  renderServices(); renderCounters(); renderExtra();
}

function renderServices() {
  const tb = $('#tbl-svc tbody');
  tb.innerHTML = '';
  for (const [code, s] of Object.entries(cfg.services)) tb.appendChild(svcRow(code, s));
}
function svcRow(code, s) {
  const tr = document.createElement('tr');
  tr.className = 'border-b';
  tr.innerHTML = `
    <td class="p-1"><input value="${code}" class="c-code w-16 border rounded px-2 py-1 font-mono uppercase"></td>
    <td class="p-1"><input value="${esc(s.name || '')}" class="c-name w-full border rounded px-2 py-1"></td>
    <td class="p-1"><input value="${esc(s.short || '')}" class="c-short w-32 border rounded px-2 py-1"></td>
    <td class="p-1"><input type="color" value="${s.color || '#0b5fa5'}" class="c-color h-9 w-12 border rounded"></td>
    <td class="p-1"><input type="number" value="${s.daily_limit || 0}" class="c-limit w-20 border rounded px-2 py-1"></td>
    <td class="p-1 text-center"><input type="checkbox" ${s.active ? 'checked' : ''} class="c-active w-5 h-5"></td>
    <td class="p-1"><button class="del text-red-600 text-sm">Xoá</button></td>`;
  tr.querySelector('.del').addEventListener('click', () => tr.remove());
  return tr;
}
$('#add-svc').addEventListener('click', () =>
  $('#tbl-svc tbody').appendChild(svcRow('', { name: '', short: '', color: '#0b5fa5', daily_limit: 100, active: true })));

function renderCounters() {
  const tb = $('#tbl-cnt tbody');
  tb.innerHTML = '';
  for (const [name, c] of Object.entries(cfg.counters)) tb.appendChild(cntRow(name, c));
}
function cntRow(name, c) {
  const tr = document.createElement('tr');
  tr.className = 'border-b';
  tr.innerHTML = `
    <td class="p-1"><input value="${esc(name)}" class="c-name w-36 border rounded px-2 py-1"></td>
    <td class="p-1"><input value="${esc(c.prefix || '')}" class="c-prefix w-40 border rounded px-2 py-1 font-mono uppercase"></td>
    <td class="p-1"><input value="${esc(c.staff || '')}" class="c-staff w-40 border rounded px-2 py-1"></td>
    <td class="p-1"><input type="number" value="${c.display_order || 1}" class="c-order w-16 border rounded px-2 py-1"></td>
    <td class="p-1 text-center"><input type="checkbox" ${c.active ? 'checked' : ''} class="c-active w-5 h-5"></td>
    <td class="p-1"><button class="del text-red-600 text-sm">Xoá</button></td>`;
  tr.querySelector('.del').addEventListener('click', () => tr.remove());
  return tr;
}
$('#add-cnt').addEventListener('click', () =>
  $('#tbl-cnt tbody').appendChild(cntRow('Quầy số 0' + (Object.keys(cfg.counters).length + 1),
    { prefix: '', staff: '', display_order: Object.keys(cfg.counters).length + 1, active: true })));

function renderExtra() {
  const box = $('#extra-fields');
  box.innerHTML = '';
  for (const [k, label] of Object.entries(EXTRA_TEXT)) {
    box.insertAdjacentHTML('beforeend', `<label class="text-sm"><span class="font-semibold block mb-1">${label}</span>
      <input data-ex="${k}" value="${esc(cfg.extra[k] ?? '')}" class="w-full border rounded px-2 py-1.5"></label>`);
  }
  for (const [k, label] of Object.entries(EXTRA_NUM)) {
    box.insertAdjacentHTML('beforeend', `<label class="text-sm"><span class="font-semibold block mb-1">${label}</span>
      <input data-ex="${k}" data-num="1" type="number" step="0.05" value="${cfg.extra[k] ?? 0}" class="w-full border rounded px-2 py-1.5"></label>`);
  }
  for (const [k, label] of Object.entries(EXTRA_BOOL)) {
    box.insertAdjacentHTML('beforeend', `<label class="text-sm flex items-center gap-2 mt-5">
      <input data-ex="${k}" data-bool="1" type="checkbox" ${cfg.extra[k] ? 'checked' : ''} class="w-5 h-5"> ${label}</label>`);
  }
  $('#extra-slots').value = JSON.stringify(cfg.extra.time_slots || [], null, 1);
}

/* -------------------------------------------------- lưu */
$('#btn-save').addEventListener('click', async () => {
  const services = {};
  for (const tr of $$('#tbl-svc tbody tr')) {
    const code = tr.querySelector('.c-code').value.trim().toUpperCase();
    if (!code) continue;
    const prev = cfg.services[code] || {};
    services[code] = {
      ...prev,
      name: tr.querySelector('.c-name').value.trim(),
      short: tr.querySelector('.c-short').value.trim(),
      color: tr.querySelector('.c-color').value,
      daily_limit: +tr.querySelector('.c-limit').value || 0,
      active: tr.querySelector('.c-active').checked,
      current_count: prev.current_count || 0,
    };
  }
  const counters = {};
  for (const tr of $$('#tbl-cnt tbody tr')) {
    const name = tr.querySelector('.c-name').value.trim();
    if (!name) continue;
    counters[name] = {
      prefix: tr.querySelector('.c-prefix').value.trim().toUpperCase(),
      staff: tr.querySelector('.c-staff').value.trim(),
      display_order: +tr.querySelector('.c-order').value || 1,
      active: tr.querySelector('.c-active').checked,
    };
  }
  const extra = {};
  for (const el of $$('#extra-fields [data-ex]')) {
    if (el.dataset.bool) extra[el.dataset.ex] = el.checked;
    else if (el.dataset.num) extra[el.dataset.ex] = +el.value;
    else extra[el.dataset.ex] = el.value;
  }
  try { extra.time_slots = JSON.parse($('#extra-slots').value || '[]'); }
  catch (_) { return msg('Khung giờ JSON không hợp lệ.', true); }

  const payload = { services, counters, extra };
  if ($('#new-pw').value.trim()) payload.new_password = $('#new-pw').value.trim();
  try {
    await api('/api/admin/config', { method: 'POST', body: payload });
    msg('Đã lưu.'); $('#new-pw').value = ''; await load();
  } catch (e) { msg(e.message, true); }
});
function msg(t, err) { const el = $('#save-msg'); el.textContent = t; el.className = 'self-center text-sm ' + (err ? 'text-red-600' : 'text-emerald-600'); }

/* -------------------------------------------------- thống kê */
async function loadStats() {
  const s = await api('/api/admin/stats');
  $('#stats-today').innerHTML = `<div class="mb-2">Thời gian chờ trung bình: <b>${Math.round(s.avg_wait_seconds / 60 * 10) / 10} phút</b></div>` +
    '<table class="w-full border-collapse"><thead><tr class="bg-slate-50 text-left border-b">' +
    '<th class="p-2">Dịch vụ</th><th class="p-2">Đã cấp</th><th class="p-2">Xong</th><th class="p-2">Vắng</th><th class="p-2">Đang chờ</th></tr></thead><tbody>' +
    s.by_service.map(r => `<tr class="border-b"><td class="p-2 font-mono">${r.prefix}</td><td class="p-2">${r.issued}</td><td class="p-2">${r.done || 0}</td><td class="p-2">${r.missed || 0}</td><td class="p-2">${r.waiting || 0}</td></tr>`).join('') +
    '</tbody></table>';
  $('#stats-visitors').innerHTML = '<table class="w-full"><tbody>' +
    s.visitors.map(v => `<tr class="border-b"><td class="p-1.5">${v.date}</td><td class="p-1.5 text-right font-mono">${v.count}</td></tr>`).join('') + '</tbody></table>';
}
$('#btn-reset').addEventListener('click', async () => {
  if (!confirm('Xoá toàn bộ số đã cấp trong hôm nay? Không thể hoàn tác.')) return;
  await api('/api/admin/reset-today', { method: 'POST' });
  loadStats();
});

function esc(s) { return String(s).replace(/"/g, '&quot;').replace(/</g, '&lt;'); }
