/* Tiện ích dùng chung: kết nối SSE, đọc số tiếng Việt, chuông báo. */

/* Mã chi nhánh do template nhúng vào (window.__BRANCH__). */
export const BRANCH = (typeof window !== 'undefined' && window.__BRANCH__) || '';

/* Ghép đường dẫn API theo chi nhánh: bpath('/ticket') -> '/api/b/<code>/ticket' */
export function bpath(p) {
  return '/api/b/' + encodeURIComponent(BRANCH) + p;
}

export function connectStream(onEvent) {
  let es = null;
  let retry = 0;
  function open() {
    es = new EventSource(bpath('/stream'));
    es.onopen = () => { retry = 0; };
    es.onmessage = (e) => {
      if (!e.data) return;
      try { onEvent(JSON.parse(e.data)); } catch (_) {}
    };
    es.onerror = () => {
      es.close();
      retry = Math.min(retry + 1, 6);
      setTimeout(open, 1000 * retry);
      onEvent({ type: '_disconnected' });
    };
  }
  open();
  return () => es && es.close();
}

export async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (res.status === 401 || res.status === 403) {
    location.href = '/login?next=' + encodeURIComponent(location.pathname);
    throw new Error('Cần đăng nhập');
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || ('Lỗi ' + res.status));
  return data;
}

/* ------------------------------------------------------- đọc số tiếng Việt */
const ONES = ['không', 'một', 'hai', 'ba', 'bốn', 'năm', 'sáu', 'bảy', 'tám', 'chín'];

// Đọc số nguyên 0..999 thành chữ (dùng cho số quầy)
export function docSo(n) {
  n = parseInt(n, 10);
  if (isNaN(n)) return '';
  if (n < 10) return ONES[n];
  if (n < 20) {
    const d = n % 10;
    if (d === 0) return 'mười';
    if (d === 5) return 'mười lăm';
    return 'mười ' + ONES[d];
  }
  if (n < 100) {
    const c = Math.floor(n / 10), d = n % 10;
    let s = ONES[c] + ' mươi';
    if (d === 1) s += ' mốt';
    else if (d === 4) s += ' tư';
    else if (d === 5) s += ' lăm';
    else if (d > 0) s += ' ' + ONES[d];
    return s;
  }
  const tr = Math.floor(n / 100), rest = n % 100;
  let s = ONES[tr] + ' trăm';
  if (rest === 0) return s;
  if (rest < 10) return s + ' lẻ ' + ONES[rest];
  return s + ' ' + docSo(rest);
}

// "A-025" -> "A không hai mươi lăm"  (chữ cái + hàng trăm đọc rời + 2 số cuối đọc gộp)
export function docSoThuTu(fullNo) {
  const m = String(fullNo).toUpperCase().match(/^([A-Z]+)[-\s]?0*(\d+)$/);
  if (!m) return String(fullNo);
  const letter = m[1].split('').join(' ');
  const s = String(parseInt(m[2], 10)).padStart(3, '0');   // "025"
  const head = ONES[+s[0]];                                  // "không"
  const tail = docSo(parseInt(s.slice(1), 10) || 0);         // docSo(25) -> "hai mươi lăm"
  return `${letter} ${head} ${tail}`;
}

/* ------------------------------------------------------- chuông + giọng nói */
let audioCtx = null;
export function chime() {
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    const ctx = audioCtx;
    const now = ctx.currentTime;
    [880, 1174, 1568].forEach((f, i) => {
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.type = 'sine'; o.frequency.value = f;
      o.connect(g); g.connect(ctx.destination);
      const t = now + i * 0.16;
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(0.3, t + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, t + 0.34);
      o.start(t); o.stop(t + 0.36);
    });
  } catch (_) {}
}

let viVoice = null;
function pickViVoice() {
  if (!('speechSynthesis' in window)) return;
  const voices = speechSynthesis.getVoices();
  viVoice = voices.find(v => /vi[-_]VN/i.test(v.lang) || /vietnam/i.test(v.name)) ||
            voices.find(v => v.lang && v.lang.toLowerCase().startsWith('vi')) || null;
}
if ('speechSynthesis' in window) {
  pickViVoice();
  speechSynthesis.onvoiceschanged = pickViVoice;
  // Giọng "Online (Natural)" của Edge nạp trễ — dò lại vài lần trong ~12 giây đầu.
  let tries = 0;
  const t = setInterval(() => {
    pickViVoice();
    if (viVoice || ++tries > 24) clearInterval(t);
  }, 500);
}

// Tên giọng tiếng Việt đang dùng ('' nếu chưa có) — để hiển thị cảnh báo.
export function viVoiceName() {
  return viVoice ? (viVoice.name || 'vi-VN') : '';
}

export function speak(text, { rate = 0.95, repeat = 2, gap = 700 } = {}) {
  if (!('speechSynthesis' in window)) return;
  pickViVoice();  // luôn lấy giọng mới nhất ngay trước khi đọc
  speechSynthesis.cancel();
  let i = 0;
  const sayOnce = () => {
    const u = new SpeechSynthesisUtterance(text);
    u.lang = 'vi-VN';
    if (viVoice) u.voice = viVoice;
    u.rate = rate; u.pitch = 1;
    u.onend = () => {
      i += 1;
      if (i < repeat) setTimeout(sayOnce, gap);
    };
    speechSynthesis.speak(u);
  };
  sayOnce();
}

/* Đọc số: ưu tiên giọng do MÁY CHỦ tạo (mode 'server'); lỗi thì quay về giọng
   trình duyệt. Máy nối TV không cần cài giọng đọc tiếng Việt.
   Trả về URL mp3 đang dùng (để trang có thể tự kiểm tra). */
let ttsAudio = null;
export function ttsUrl(text, voice = '') {
  return bpath('/tts?text=' + encodeURIComponent(text) + (voice ? '&voice=' + encodeURIComponent(voice) : ''));
}
export function speakVi(text, { rate = 1, repeat = 2, gap = 600, mode = 'server', voice = '' } = {}) {
  if (mode !== 'server') { speak(text, { rate: rate * 0.95, repeat, gap: gap + 100 }); return; }
  try { if (ttsAudio) ttsAudio.pause(); } catch (_) {}
  const url = ttsUrl(text, voice);
  let i = 0, fellBack = false;
  const fallback = () => {
    if (fellBack || i > 0) return;
    fellBack = true;
    speak(text, { rate: rate * 0.95, repeat, gap: gap + 100 });
  };
  const playOnce = () => {
    const a = new Audio(url);
    ttsAudio = a;
    a.playbackRate = Math.min(1.5, Math.max(0.6, rate));
    a.addEventListener('ended', () => { i += 1; if (i < repeat) setTimeout(playOnce, gap); });
    a.addEventListener('error', fallback);
    const p = a.play();
    if (p && p.catch) p.catch(fallback);
  };
  playOnce();
}

// Ghép câu đọc từ mẫu {so} / {quay}
export function buildCallSentence(template, fullNo, counterNo) {
  return (template || 'Xin mời số thứ tự {so}, đến quầy số {quay}')
    .replace('{so}', docSoThuTu(fullNo))
    .replace('{quay}', docSo(counterNo));
}

export function fmtTime(s) {
  if (!s) return '';
  const d = new Date(s.replace(' ', 'T'));
  if (isNaN(d)) return s.slice(11, 16);
  return d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
}

export function elapsed(s) {
  if (!s) return '';
  const d = new Date(s.replace(' ', 'T'));
  const sec = Math.max(0, Math.floor((Date.now() - d.getTime()) / 1000));
  const m = Math.floor(sec / 60), ss = sec % 60;
  return `${m}:${String(ss).padStart(2, '0')}`;
}
