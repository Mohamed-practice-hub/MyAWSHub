async function load(){
  const url = document.getElementById('apiUrl').value.trim();
  if(!url){ alert('Enter API URL'); return; }
  const res = await fetch(url);
  if(!res.ok){ alert('Failed: '+res.status); return; }
  const data = await res.json();
  const tbody = document.querySelector('#historyTable tbody');
  tbody.innerHTML = '';
  (data.orders||[]).forEach(od=>{
    const tr = document.createElement('tr');
    const td = (t)=>{ const e=document.createElement('td'); e.textContent=t??''; return e; };
    tr.append(
      td(od.order_timestamp||od.exchange_timestamp||''),
      td(od.tradingsymbol||od.symbol||''),
      td(od.transaction_type||od.side||''),
      td(od.quantity||od.filled_quantity||od.qty||''),
      td(od.status||''),
      td(od.average_price||od.price||''),
      td(od.reason||od.tag||''),
      td(od.order_id||od.id||'')
    );
    tbody.appendChild(tr);
  });
}

document.getElementById('loadBtn').addEventListener('click', load);
