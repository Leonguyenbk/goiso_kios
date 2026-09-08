/* Trang tra cứu / huỷ lịch hẹn (/lich-hen/<token>). */
const $ = (s) => document.querySelector(s);
const token = window.__TOKEN__;

const LABELS = {
  booked: ['Đang chờ đến hẹn', 'bg-amber-100 text-amber-700'],
  checked_in: ['Đã check-in — đã có số', 'bg-emerald-100 text-emerald-700'],
  cancelled: ['Đã huỷ', 'bg-slate-200 text-slate-600'],
  expired: ['Đã hết hạn (quá giờ hẹn)', 'bg-red-100 text-red-700'],
};

async function load() {
  let d;
  try {
    const r = await fetch('/api/booking/appt/' + encodeURIComponent(token));
    d = await r.json();
    if (!r.ok) throw new Error(d.error || 'Không tải được');
  } catch (e) {
    $('#loading').classList.add('hidden');
    $('#err').textContent = e.message; $('#err').classList.remove('hidden');
    return;
  }
  $('#loading').classList.add('hidden');
  $('#body').classList.remove('hidden');
  $('#code').textContent = d.code;
  const [txt, cls] = LABELS[d.status] || [d.status, 'bg-slate-200'];
  $('#status').textContent = txt; $('#status').className = 'inline-block text-xs font-semibold rounded px-2 py-1 ' + cls;
  $('#v-branch').textContent = d.branch_name;
  $('#v-svc').textContent = d.service_short;
  $('#v-date').textContent = d.slot_date;
  $('#v-slot').textContent = d.slot_start + '–' + d.slot_end;
  $('#v-name').textContent = d.citizen_name;
  if (d.queue_no) { $('#v-qno').textContent = d.queue_no; $('#row-qno').classList.remove('hidden'); }

  if (d.status === 'booked') {
    new QRCode($('#qr'), { text: location.href, width: 168, height: 168 });
    const b = $('#btn-cancel');
    b.classList.remove('hidden');
    b.addEventListener('click', async () => {
      if (!confirm('Huỷ lịch hẹn này?')) return;
      const r = await fetch('/api/booking/appt/' + encodeURIComponent(token) + '/cancel', { method: 'POST' });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) { alert(j.error || 'Không huỷ được'); return; }
      location.reload();
    });
  }
}
load();
