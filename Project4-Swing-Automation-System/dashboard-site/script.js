(function(){
  const tableBody = document.querySelector('#historyTable tbody');
  const statusEl = document.querySelector('#status');
  const apiInput = document.querySelector('#apiUrl');
  const btn = document.querySelector('#loadBtn');

  function fmt(x) { return x ?? ''; }
  function setStatus(msg, cls) { statusEl.textContent = msg; statusEl.className = cls || ''; }

  async function load() {
    const url = (apiInput.value || '').trim();
    if (!url) { setStatus('Enter API URL then Load', 'error'); return; }
    let endpoint = url;
    // Allow either full URL to function root or direct invoke URL expecting JSON response at /
    if (!endpoint.endsWith('/')) endpoint += '/';
    setStatus('Loading...', '');
    tableBody.innerHTML = '';
    try {
      const resp = await fetch(endpoint, { headers: { 'Accept': 'application/json' } });
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      const data = await resp.json();
      const records = data.records || [];
      for (const r of records) {
        const tr = document.createElement('tr');
        const cells = [
          fmt(r.submitted_at),
          fmt(r.filled_at),
          fmt(r.symbol),
          fmt(r.side),
          fmt(r.qty),
          fmt(r.status),
          fmt(r.filled_avg_price),
          fmt(r.realized_pl),
          fmt(r.type),
          fmt(r.reason?.source),
          fmt(r.reason?.signal_price),
          fmt(r.reason?.signal_volume),
          fmt(r.reason?.received_at)
        ];
        for (const c of cells) {
          const td = document.createElement('td');
          td.textContent = c;
          if (cells.indexOf(c) === 8) { // realized P/L column (0-based)
            const val = parseFloat(c);
            if (!isNaN(val)) {
              td.style.color = val >= 0 ? 'green' : 'crimson';
            }
          }
          tr.appendChild(td);
        }
        tableBody.appendChild(tr);
      }
      setStatus(`Loaded ${records.length} records since ${fmt(data.since)}`, 'ok');
    } catch (err) {
      console.error(err);
      setStatus('Error: ' + err.message, 'error');
    }
  }

  btn.addEventListener('click', load);
})();
