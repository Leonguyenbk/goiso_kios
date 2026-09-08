const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' }, ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (res.status === 401 || res.status === 403) { location.href = '/login?next=/admin'; throw new Error('Cần đăng nhập'); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || ('Lỗi ' + res.status));
  return data;
}
function esc(s) { return String(s ?? '').replace(/"/g, '&quot;').replace(/</g, '&lt;'); }

let branches = [];
let curCode = null;
let cfg = { services: {}, counters: {}, extra: {} };

const EXTRA_TEXT = {
  ten_co_quan: 'Tên cơ quan', link_qr: 'Link QR trên phiếu',
  counter_pin: 'Mã PIN quầy (để trống = không yêu cầu)',
  lock_message: 'Thông báo ngoài giờ', voice_template: 'Mẫu câu đọc ({so}, {quay})',
  tts_mode: 'Chế độ đọc số: server (máy chủ) / browser (trình duyệt)',
  tts_voice: 'Giọng máy chủ: vi-VN-HoaiMyNeural (nữ) / vi-VN-NamMinhNeural (nam)',
  footer_credit: 'Dòng ghi công ở chân màn hình (2 dòng, gõ \\n để xuống dòng)',
};
const EXTRA_BOOL = {
  lock_time_enabled: 'Khoá theo giờ', qr_enabled: 'In mã QR',
  allow_saturday: 'Cho phép Thứ Bảy', allow_sunday: 'Cho phép Chủ nhật',
};
const EXTRA_NUM = {
  voice_rate: 'Tốc độ đọc (0.5–1.5)', voice_repeat: 'Số lần đọc lặp',
  spotlight_seconds: 'Giữ spotlight (giây)', recent_count: 'Số lượt hiển thị gần đây',
};

/* -------------------------------------------------- đăng xuất */
$('#btn-logout').addEventListener('click', async () => {
  try { await fetch('/api/logout', { method: 'POST' }); } catch (_) {}
  location.href = '/login';
});

/* -------------------------------------------------- tabs */
$$('.tab').forEach(b => b.addEventListener('click', () => activateTab(b.dataset.tab)));
function activateTab(tab) {
  $$('.tab').forEach(x => {
    const on = x.dataset.tab === tab;
    x.classList.toggle('bg-gov', on); x.classList.toggle('text-white', on);
    x.classList.toggle('bg-white', !on); x.classList.toggle('border', !on);
  });
  $$('[data-panel]').forEach(p => p.classList.toggle('hidden', p.dataset.panel !== tab));
  const isCfg = ['services', 'counters', 'extra', 'booking'].includes(tab);
  $('#branch-bar').classList.toggle('hidden', !isCfg);
  $('#save-bar').classList.toggle('hidden', !isCfg);
  if (tab === 'stats') loadStats();
  if (tab === 'users') loadUsers();
}

/* -------------------------------------------------- người dùng */
let userBranches = [];
async function loadUsers() {
  const d = await api('/api/admin/users');
  userBranches = d.branches;
  const tb = $('#tbl-user tbody');
  tb.innerHTML = '';
  d.users.forEach(u => tb.appendChild(userRow(u)));
}
function branchOptions(sel) {
  return '<option value="">— (admin, không cần) —</option>' +
    userBranches.map(b => `<option value="${b.code}" ${b.code === sel ? 'selected' : ''}>${esc(b.name)}</option>`).join('');
}
function userRow(u) {
  const tr = document.createElement('tr');
  tr.className = 'border-b';
  const isNew = !u.username;
  tr.innerHTML = `
    <td class="p-1"><input value="${esc(u.username)}" class="u-name w-32 border rounded px-2 py-1 font-mono lowercase" ${isNew ? '' : 'readonly'}></td>
    <td class="p-1"><input value="${esc(u.full_name)}" class="u-full w-56 border rounded px-2 py-1"></td>
    <td class="p-1"><select class="u-role border rounded px-2 py-1">
      <option value="staff" ${u.role !== 'admin' ? 'selected' : ''}>staff</option>
      <option value="admin" ${u.role === 'admin' ? 'selected' : ''}>admin</option></select></td>
    <td class="p-1"><select class="u-branch border rounded px-2 py-1">${branchOptions(u.branch_code)}</select></td>
    <td class="p-1"><input type="text" class="u-pw w-32 border rounded px-2 py-1" placeholder="${isNew ? 'bắt buộc' : 'để trống = giữ'}"></td>
    <td class="p-1 text-center"><input type="checkbox" class="u-active w-5 h-5" ${u.active !== false ? 'checked' : ''}></td>
    <td class="p-1 whitespace-nowrap">
      <button class="u-save btn bg-gov text-white px-2 py-1 text-xs">${isNew ? 'Tạo' : 'Lưu'}</button>
      ${isNew ? '' : '<button class="u-del text-red-600 text-xs ml-1">Xoá</button>'}
    </td>`;
  tr.querySelector('.u-save').addEventListener('click', async () => {
    const body = {
      action: isNew ? 'create' : 'update',
      username: tr.querySelector('.u-name').value.trim().toLowerCase(),
      full_name: tr.querySelector('.u-full').value.trim(),
      role: tr.querySelector('.u-role').value,
      branch_code: tr.querySelector('.u-branch').value || null,
      password: tr.querySelector('.u-pw').value,
      active: tr.querySelector('.u-active').checked,
    };
    try { await api('/api/admin/users', { method: 'POST', body }); await loadUsers(); }
    catch (e) { alert(e.message); }
  });
  if (!isNew) tr.querySelector('.u-del').addEventListener('click', async () => {
    if (!confirm(`Xoá tài khoản "${u.username}"?`)) return;
    try { await api('/api/admin/users', { method: 'POST', body: { action: 'delete', username: u.username } }); await loadUsers(); }
    catch (e) { alert(e.message); }
  });
  return tr;
}
$('#add-user').addEventListener('click', () =>
  $('#tbl-user tbody').appendChild(userRow({ username: '', full_name: '', role: 'staff', branch_code: '', active: true })));

/* -------------------------------------------------- chi nhánh */
async function loadBranches() {
  branches = (await api('/api/admin/branches')).branches;
  renderBranchTable();
  const opts = branches.map(b => `<option value="${b.code}">${esc(b.name)} (${b.code})</option>`).join('');
  $('#sel-branch').innerHTML = opts || '<option value="">— chưa có chi nhánh —</option>';
  $('#sel-stats-branch').innerHTML = '<option value="all">Tất cả chi nhánh</option>' + opts;
  if (branches.length) {
    if (!branches.find(b => b.code === curCode)) curCode = branches[0].code;
    $('#sel-branch').value = curCode;
    await loadBranchConfig(curCode);
  }
}

$('#sel-branch').addEventListener('change', () => loadBranchConfig($('#sel-branch').value));

function renderBranchTable() {
  const tb = $('#tbl-branch tbody');
  tb.innerHTML = '';
  branches.forEach(b => tb.appendChild(branchRow(b)));
}
function branchRow(b) {
  const tr = document.createElement('tr');
  tr.className = 'border-b align-top';
  const isNew = !b.code;
  tr.innerHTML = `
    <td class="p-1"><input value="${esc(b.code)}" class="b-code w-24 border rounded px-2 py-1 font-mono lowercase" ${isNew ? '' : 'readonly'}></td>
    <td class="p-1"><input value="${esc(b.name)}" class="b-name w-32 border rounded px-2 py-1"></td>
    <td class="p-1"><input value="${esc(b.full_name)}" class="b-full w-64 border rounded px-2 py-1"></td>
    <td class="p-1"><input value="${esc(b.address)}" class="b-addr w-48 border rounded px-2 py-1"></td>
    <td class="p-1"><input type="number" value="${b.display_order ?? 99}" class="b-order w-14 border rounded px-2 py-1"></td>
    <td class="p-1 text-center"><input type="checkbox" ${b.active !== false ? 'checked' : ''} class="b-active w-5 h-5"></td>
    <td class="p-1 text-xs text-slate-500">
      ${isNew ? '<span class="text-slate-400">tạo xong sẽ có khoá</span>' : `
      <div>API: <code class="b-key">${esc((b.api_key || '').slice(0, 10))}…</code>
        <button class="regen-key text-gov underline">tạo lại</button></div>
      <div>DISPLAY: <code class="b-dtok">${esc(b.display_token || '')}</code>
        <button class="regen-dtok text-gov underline">tạo lại</button></div>`}
    </td>
    <td class="p-1 whitespace-nowrap">
      <button class="save-b btn bg-gov text-white px-2 py-1 text-xs">${isNew ? 'Tạo' : 'Lưu'}</button>
      ${isNew ? '' : '<button class="del-b text-red-600 text-xs ml-1">Xoá</button>'}
    </td>`;

  tr.querySelector('.save-b').addEventListener('click', async () => {
    const body = {
      code: tr.querySelector('.b-code').value.trim().toLowerCase(),
      name: tr.querySelector('.b-name').value.trim(),
      full_name: tr.querySelector('.b-full').value.trim(),
      address: tr.querySelector('.b-addr').value.trim(),
      display_order: +tr.querySelector('.b-order').value || 99,
      active: tr.querySelector('.b-active').checked,
      action: isNew ? 'create' : 'update',
    };
    try {
      await api('/api/admin/branches', { method: 'POST', body });
      curCode = body.code;
      await loadBranches();
    } catch (e) { alert(e.message); }
  });
  if (!isNew) {
    tr.querySelector('.del-b').addEventListener('click', async () => {
      if (!confirm(`Xoá chi nhánh "${b.name}" và toàn bộ dữ liệu của nó? Không thể hoàn tác.`)) return;
      await api('/api/admin/branches', { method: 'POST', body: { action: 'delete', code: b.code } });
      await loadBranches();
    });
    tr.querySelector('.regen-key').addEventListener('click', async () => {
      if (!confirm('Tạo lại API key? Kiosk chi nhánh này phải cập nhật config.json.')) return;
      const r = await api('/api/admin/branches', { method: 'POST', body: { action: 'regen_key', code: b.code } });
      alert('API key mới:\n' + r.value); await loadBranches();
    });
    tr.querySelector('.regen-dtok').addEventListener('click', async () => {
      const r = await api('/api/admin/branches', { method: 'POST', body: { action: 'regen_display_token', code: b.code } });
      alert('Display token mới: ' + r.value); await loadBranches();
    });
  }
  return tr;
}
$('#add-branch').addEventListener('click', () =>
  $('#tbl-branch tbody').appendChild(branchRow({ code: '', name: '', full_name: '', address: '', display_order: (branches.length + 1) })));

/* -------------------------------------------------- nạp cấu hình 1 chi nhánh */
async function loadBranchConfig(code) {
  if (!code) return;
  curCode = code;
  cfg = await api(`/api/admin/b/${encodeURIComponent(code)}/config`);
  $('#lnk-display').href = `/b/${code}/display`;
  $('#lnk-counter').href = `/b/${code}/counter`;
  renderServices(); renderCounters(); renderExtra(); renderBooking();
}

/* -------------------------------------------------- đặt lịch online */
const BK_BOOL = { enabled: 'Mở đặt lịch online', online_priority: 'Ưu tiên số đặt lịch khi gọi', turnstile: 'Bật Turnstile chống spam' };
const BK_NUM = {
  open_days_ahead: 'Cho đặt trước tối đa (ngày)', slot_minutes: 'Độ dài mỗi khung (phút)',
  max_active_per_cccd: 'Số lịch đang chờ tối đa / CCCD', checkin_grace_minutes: 'Ân hạn check-in (phút)',
};
function renderBooking() {
  const bk = cfg.booking || {};
  const box = $('#bk-fields'); box.innerHTML = '';
  for (const [k, label] of Object.entries(BK_NUM)) {
    box.insertAdjacentHTML('beforeend', `<label class="text-sm"><span class="font-semibold block mb-1">${label}</span>
      <input data-bk="${k}" data-num="1" type="number" value="${bk[k] ?? 0}" class="w-full border rounded px-2 py-1.5"></label>`);
  }
  for (const [k, label] of Object.entries(BK_BOOL)) {
    box.insertAdjacentHTML('beforeend', `<label class="text-sm flex items-center gap-2 mt-5">
      <input data-bk="${k}" data-bool="1" type="checkbox" ${bk[k] ? 'checked' : ''} class="w-5 h-5"> ${label}</label>`);
  }
  $('#bk-windows').value = JSON.stringify(bk.windows || [], null, 1);
  $('#bk-caps').value = JSON.stringify(bk.capacity_per_slot || { _default: 4 }, null, 1);
  if (!$('#bk-date').value) $('#bk-date').value = new Date().toISOString().slice(0, 10);
}
function collectBooking() {
  const out = {};
  for (const el of $$('#bk-fields [data-bk]')) {
    if (el.dataset.bool) out[el.dataset.bk] = el.checked;
    else out[el.dataset.bk] = +el.value;
  }
  out.windows = JSON.parse($('#bk-windows').value || '[]');
  out.capacity_per_slot = JSON.parse($('#bk-caps').value || '{}');
  return out;
}
$('#bk-load').addEventListener('click', loadAppts);
async function loadAppts() {
  if (!curCode) return;
  const d = $('#bk-date').value;
  const r = await api(`/api/admin/b/${encodeURIComponent(curCode)}/appointments?date=${d}`);
  const st = { booked: 'chờ', checked_in: 'đã lấy số', cancelled: 'huỷ', expired: 'hết hạn' };
  $('#bk-appts').innerHTML = r.appointments.length ? (
    '<table class="w-full border-collapse"><thead><tr class="bg-slate-50 text-left border-b">' +
    '<th class="p-2">Giờ</th><th class="p-2">Mã</th><th class="p-2">DV</th><th class="p-2">Người hẹn</th>' +
    '<th class="p-2">SĐT</th><th class="p-2">TT</th><th></th></tr></thead><tbody>' +
    r.appointments.map(a => `<tr class="border-b">
      <td class="p-2 font-mono">${a.slot_start}</td><td class="p-2 font-mono">${a.code}</td>
      <td class="p-2 font-mono">${a.prefix}</td><td class="p-2">${esc(a.citizen_name)}</td>
      <td class="p-2">${esc(a.phone)}</td><td class="p-2">${st[a.status] || a.status}</td>
      <td class="p-2">${a.status === 'booked' ? `<button class="del-appt text-red-600 text-xs" data-t="${a.token}">huỷ</button>` : ''}</td>
    </tr>`).join('') + '</tbody></table>'
  ) : '<div class="text-slate-400">Không có lịch hẹn ngày này.</div>';
  $$('#bk-appts .del-appt').forEach(b => b.addEventListener('click', async () => {
    if (!confirm('Huỷ lịch hẹn này?')) return;
    await api(`/api/admin/b/${encodeURIComponent(curCode)}/appointments/cancel`, { method: 'POST', body: { token: b.dataset.t } });
    loadAppts();
  }));
}

function renderServices() {
  const tb = $('#tbl-svc tbody'); tb.innerHTML = '';
  for (const [code, s] of Object.entries(cfg.services || {})) tb.appendChild(svcRow(code, s));
}
function svcRow(code, s) {
  const tr = document.createElement('tr');
  tr.className = 'border-b';
  tr.innerHTML = `
    <td class="p-1"><input value="${esc(code)}" class="c-code w-16 border rounded px-2 py-1 font-mono uppercase"></td>
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
  const tb = $('#tbl-cnt tbody'); tb.innerHTML = '';
  for (const [name, c] of Object.entries(cfg.counters || {})) tb.appendChild(cntRow(name, c));
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
$('#add-cnt').addEventListener('click', () => {
  const n = Object.keys(cfg.counters || {}).length + 1;
  $('#tbl-cnt tbody').appendChild(cntRow('Quầy số ' + String(n).padStart(2, '0'),
    { prefix: '', staff: '', display_order: n, active: true }));
});

function renderExtra() {
  const box = $('#extra-fields'); box.innerHTML = '';
  const ex = cfg.extra || {};
  for (const [k, label] of Object.entries(EXTRA_TEXT)) {
    box.insertAdjacentHTML('beforeend', `<label class="text-sm"><span class="font-semibold block mb-1">${label}</span>
      <input data-ex="${k}" value="${esc(ex[k] ?? '')}" class="w-full border rounded px-2 py-1.5"></label>`);
  }
  for (const [k, label] of Object.entries(EXTRA_NUM)) {
    box.insertAdjacentHTML('beforeend', `<label class="text-sm"><span class="font-semibold block mb-1">${label}</span>
      <input data-ex="${k}" data-num="1" type="number" step="0.05" value="${ex[k] ?? 0}" class="w-full border rounded px-2 py-1.5"></label>`);
  }
  for (const [k, label] of Object.entries(EXTRA_BOOL)) {
    box.insertAdjacentHTML('beforeend', `<label class="text-sm flex items-center gap-2 mt-5">
      <input data-ex="${k}" data-bool="1" type="checkbox" ${ex[k] ? 'checked' : ''} class="w-5 h-5"> ${label}</label>`);
  }
  $('#extra-slots').value = JSON.stringify(ex.time_slots || [], null, 1);
}

/* -------------------------------------------------- lưu cấu hình chi nhánh */
$('#btn-save').addEventListener('click', async () => {
  if (!curCode) return msg('Chưa chọn chi nhánh.', true);
  const services = {};
  for (const tr of $$('#tbl-svc tbody tr')) {
    const code = tr.querySelector('.c-code').value.trim().toUpperCase();
    if (!code) continue;
    const prev = (cfg.services || {})[code] || {};
    services[code] = {
      ...prev,
      name: tr.querySelector('.c-name').value.trim(),
      short: tr.querySelector('.c-short').value.trim(),
      color: tr.querySelector('.c-color').value,
      daily_limit: +tr.querySelector('.c-limit').value || 0,
      active: tr.querySelector('.c-active').checked,
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
  try { payload.booking = collectBooking(); }
  catch (_) { return msg('Cấu hình đặt lịch (JSON) không hợp lệ.', true); }
  try {
    await api(`/api/admin/b/${encodeURIComponent(curCode)}/config`, { method: 'POST', body: payload });
    msg('Đã lưu chi nhánh ' + curCode + '.');
    await loadBranchConfig(curCode);
  } catch (e) { msg(e.message, true); }
});
function msg(t, err) { const el = $('#save-msg'); el.textContent = t; el.className = 'self-center text-sm ' + (err ? 'text-red-600' : 'text-emerald-600'); }

/* -------------------------------------------------- thống kê */
$('#sel-stats-branch').addEventListener('change', loadStats);
$('#btn-reset').addEventListener('click', async () => {
  const code = $('#sel-stats-branch').value;
  if (code === 'all') return;
  if (!confirm(`Xoá toàn bộ số đã cấp hôm nay của chi nhánh "${code}"? Không thể hoàn tác.`)) return;
  await api(`/api/admin/b/${encodeURIComponent(code)}/reset-today`, { method: 'POST' });
  loadStats();
});
async function loadStats() {
  const which = $('#sel-stats-branch').value || 'all';
  const s = await api('/api/admin/stats?branch=' + encodeURIComponent(which));
  const single = which !== 'all';
  $('#btn-reset').classList.toggle('hidden', !single);
  $('#stats-visitors-wrap').classList.toggle('hidden', !single);

  if (!single) {
    $('#stats-body').innerHTML =
      '<table class="w-full border-collapse"><thead><tr class="bg-slate-50 text-left border-b">' +
      '<th class="p-2">Chi nhánh</th><th class="p-2">Tổng lượt</th><th class="p-2">Chờ TB (phút)</th>' +
      '<th class="p-2">Đã cấp</th><th class="p-2">Xong</th><th class="p-2">Đang chờ</th></tr></thead><tbody>' +
      s.branches.map(b => {
        const sum = b.by_service.reduce((a, r) => ({
          issued: a.issued + r.issued, done: a.done + (r.done || 0), waiting: a.waiting + (r.waiting || 0),
        }), { issued: 0, done: 0, waiting: 0 });
        return `<tr class="border-b"><td class="p-2 font-semibold">${esc(b.name)} <span class="text-slate-400 font-mono text-xs">${b.code}</span></td>
          <td class="p-2">${b.today_total}</td><td class="p-2">${Math.round(b.avg_wait_seconds / 6) / 10}</td>
          <td class="p-2">${sum.issued}</td><td class="p-2">${sum.done}</td><td class="p-2">${sum.waiting}</td></tr>`;
      }).join('') + '</tbody></table>';
    return;
  }

  const b = s.branches[0];
  $('#stats-body').innerHTML =
    `<div class="mb-2">Chi nhánh <b>${esc(b.name)}</b> · Tổng lượt hôm nay: <b>${b.today_total}</b> · ` +
    `Thời gian chờ trung bình: <b>${Math.round(b.avg_wait_seconds / 6) / 10} phút</b></div>` +
    '<table class="w-full border-collapse"><thead><tr class="bg-slate-50 text-left border-b">' +
    '<th class="p-2">Dịch vụ</th><th class="p-2">Đã cấp</th><th class="p-2">Xong</th><th class="p-2">Vắng</th><th class="p-2">Đang chờ</th></tr></thead><tbody>' +
    b.by_service.map(r => `<tr class="border-b"><td class="p-2 font-mono">${r.prefix}</td><td class="p-2">${r.issued}</td><td class="p-2">${r.done || 0}</td><td class="p-2">${r.missed || 0}</td><td class="p-2">${r.waiting || 0}</td></tr>`).join('') +
    '</tbody></table>';
  $('#stats-visitors').innerHTML = '<table class="w-full"><tbody>' +
    s.visitors.map(v => `<tr class="border-b"><td class="p-1.5">${v.date}</td><td class="p-1.5 text-right font-mono">${v.count}</td></tr>`).join('') + '</tbody></table>';
}

/* -------------------------------------------------- khởi động (đã đăng nhập server-side) */
(async () => {
  await loadBranches();
  activateTab('branches');
})();
