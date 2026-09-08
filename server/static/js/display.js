import { connectStream, bpath, chime, speak, speakVi, buildCallSentence, docSo, fmtTime, viVoiceName } from './common.js';

const $ = (s) => document.querySelector(s);
const WEEKDAYS = ['Chủ nhật', 'Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy'];

let cfg = { voice_rate: 0.95, voice_repeat: 2, voice_template: 'Xin mời số thứ tự {so}, đến quầy số {quay}', spotlight_seconds: 20 };
let audioReady = false;
let spotlightTimer = null;
let lastCallId = null;

const params = new URLSearchParams(location.search);
if (params.get('nocursor') === '1') document.body.classList.add('nocursor');
const onlyCounters = (params.get('counters') || '').split(',').map(s => s.trim()).filter(Boolean);

/* -------------------------------------------------- đồng hồ */
function tickClock() {
  const d = new Date();
  $('#clock').textContent = d.toLocaleTimeString('vi-VN', { hour12: false });
  $('#date').textContent = `${WEEKDAYS[d.getDay()]}, ngày ${d.getDate()}/${d.getMonth() + 1}/${d.getFullYear()}`;
}
setInterval(tickClock, 1000);
tickClock();

/* -------------------------------------------------- cổng mở đầu */
function openGate() {
  audioReady = true;
  chime();
  const el = document.documentElement;
  if (el.requestFullscreen) el.requestFullscreen().catch(() => {});
  $('#gate').remove();
  fetch(bpath('/config/public')).then(r => r.json()).then(d => { cfg = { ...cfg, ...d.extra }; }).catch(() => {});
  checkVoice();
  setInterval(checkVoice, 4000);
}

function checkVoice() {
  const el = $('#novoice');
  if (!el) return;
  // Chế độ 'server': máy chủ tự đọc, không cần giọng trình duyệt -> không cảnh báo.
  const needBrowserVoice = (cfg.tts_mode || 'server') === 'browser';
  el.classList.toggle('hidden', !needBrowserVoice || !!viVoiceName());
}
$('#gate').addEventListener('click', openGate);
window.addEventListener('keydown', () => { if ($('#gate')) openGate(); }, { once: true });

/* -------------------------------------------------- render snapshot */
function statusBadge(s) {
  if (s === 'active') return '<span class="text-emerald-600">● Đang phục vụ</span>';
  if (s === 'paused') return '<span class="text-amber-500">● Tạm dừng</span>';
  return '<span class="text-slate-400">● Ngoài giờ / nghỉ</span>';
}

function renderGrid(counters) {
  let list = counters;
  if (onlyCounters.length) list = counters.filter(c => onlyCounters.includes(c.no) || onlyCounters.includes(c.id));
  const grid = $('#grid');
  grid.innerHTML = list.map(c => `
    <div data-counter="${c.id}" class="counter-card rounded-2xl bg-white border-2 border-slate-200 p-4 flex flex-col ${c.status === 'active' ? 'card-serving' : ''} ${c.status === 'offline' ? 'opacity-45' : ''}">
      <div class="flex items-center justify-between">
        <div class="text-2xl font-extrabold">QUẦY ${c.no}</div>
        <div class="text-sm font-semibold">${statusBadge(c.status)}</div>
      </div>
      <div class="text-sm text-slate-500 truncate" style="border-left:4px solid ${c.service_color};padding-left:6px;margin-top:4px;">${c.service_short || ''}</div>
      <div class="flex-1 flex items-center justify-center">
        <div class="font-mono font-extrabold tnum leading-none" style="font-size: clamp(2.5rem, 6vw, 5rem); color:${c.current_no ? c.service_color : '#cbd5e1'};">
          ${c.current_no || '—'}
        </div>
      </div>
      <div class="text-sm text-slate-400 text-center truncate h-5">${c.staff_name ? 'CB: ' + c.staff_name : ''}</div>
    </div>`).join('');
}

function renderTicker(recent) {
  $('#ticker').innerHTML = recent.map(r => `
    <span class="ticker-item shrink-0 rounded-lg bg-slate-100 px-3 py-1.5 text-lg font-semibold tnum font-mono flex items-center gap-2">
      <b style="color:${r.service_color}">${r.full_no}</b>
      <span class="text-slate-400">›</span> Q${r.counter_no}
    </span>`).join('') || '<span class="text-slate-400">—</span>';
}

function renderWaiting(waiting, total) {
  $('#waiting').innerHTML = waiting.map(w => `
    <span class="flex items-center gap-2">
      <span class="inline-block w-3 h-3 rounded-full" style="background:${w.color}"></span>
      ${w.prefix}: <b class="tnum font-mono text-2xl">${w.count}</b>
    </span>`).join('') || '<span class="opacity-70">Không có</span>';
  $('#total').textContent = total;
}

function applySnapshot(s) {
  renderGrid(s.counters);
  renderTicker(s.recent);
  renderWaiting(s.waiting, s.today_total);
}

/* -------------------------------------------------- xử lý lượt gọi */
function showSpotlight(ev) {
  $('#sp-empty').classList.add('hidden');
  const body = $('#sp-body');
  body.classList.remove('hidden'); body.classList.add('flex');
  $('#sp-number').textContent = ev.full_no;
  $('#sp-number').style.color = ev.service_color || '#0b5fa5';
  $('#sp-counter').textContent = 'QUẦY ' + ev.counter_no;
  $('#sp-service').textContent = ev.service_name || '';
  const sp = $('#spotlight');
  sp.classList.remove('slide-in'); void sp.offsetWidth; sp.classList.add('slide-in');
  sp.style.borderColor = ev.service_color || '#0b5fa5';

  // nhấp nháy thẻ quầy tương ứng
  document.querySelectorAll('.counter-card').forEach(el => el.classList.remove('pulse-card'));
  const card = document.querySelector(`.counter-card[data-counter="${CSS.escape(ev.counter_id)}"]`);
  if (card) { void card.offsetWidth; card.classList.add('pulse-card'); }

  clearTimeout(spotlightTimer);
  spotlightTimer = setTimeout(() => { sp.style.opacity = '0.55'; }, (cfg.spotlight_seconds || 20) * 1000);
  sp.style.opacity = '1';
}

function announce(ev) {
  if (!audioReady) return;
  chime();
  const text = buildCallSentence(cfg.voice_template, ev.full_no, ev.counter_no);
  setTimeout(() => speakVi(text, {
    rate: cfg.voice_rate, repeat: cfg.voice_repeat,
    mode: cfg.tts_mode || 'server', voice: cfg.tts_voice || '',
  }), 650);
}

/* -------------------------------------------------- luồng SSE */
connectStream((ev) => {
  if (ev.type === 'snapshot') {
    $('#conn').classList.add('hidden');
    applySnapshot(ev);
  } else if (ev.type === 'call') {
    // tránh phát lặp nếu nhận trùng
    const key = ev.id + '|' + (ev.is_recall ? 't' + Date.now() : 'n');
    if (key === lastCallId) return;
    lastCallId = key;
    showSpotlight(ev);
    announce(ev);
  } else if (ev.type === '_disconnected') {
    $('#conn').classList.remove('hidden');
  }
});

// tự tải lại lúc 0h05 để reset ngày mới
setInterval(() => {
  const d = new Date();
  if (d.getHours() === 0 && d.getMinutes() === 5) location.reload();
}, 60000);
