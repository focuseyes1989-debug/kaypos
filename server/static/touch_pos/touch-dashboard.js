(() => {
  'use strict';
  let root, ctx, sequence = 0;
  const date = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  const money = n => Number(n || 0).toLocaleString(undefined, {maximumFractionDigits:2});
  function breakdown(title, rows) {
    return `<section class="panel dashboard-breakdown"><h3>${ctx.escapeHtml(title)}</h3>${rows.length ? rows.map(r=>`<div><span>${ctx.escapeHtml(r.label)}<small>${money(r.count)} records</small></span><strong>${money(r.total)} Ks</strong></div>`).join('') : '<p>No records for this period.</p>'}</section>`;
  }
  function render(data) {
    const p=data.period || {}, e=data.expenses || {};
    const cards=[['Sales',p.sales,'Completed sales total after refunds'],['Completed sales',p.transactions,'Number of completed transactions',true],['Expenses',e.total,`${money(e.count)} expense records`],['Sales less expenses',Number(p.sales||0)-Number(e.total||0),'Before cost of goods; not net profit']];
    root.querySelector('[data-results]').innerHTML=`<div class="dashboard-cards">${cards.map(([label,value,note,count])=>`<article class="panel"><span>${label}</span><strong>${money(value)}${count?'':' Ks'}</strong><small>${note}</small></article>`).join('')}</div><section class="panel dashboard-summary"><h3>Sales summary</h3><div><span>Sales including refunded receipts</span><strong>${money(p.gross_sales)} Ks</strong></div><div><span>Refunded receipts</span><strong>${money(p.refunds)} Ks</strong></div><div><span>Average completed sale</span><strong>${money(p.transactions ? p.sales/p.transactions : 0)} Ks</strong></div><small>Sales use the receipt date; expenses use the expense date. Refunded receipts are excluded from completed sales.</small></section><div class="dashboard-columns">${breakdown('Sales by payment type',data.payment_sales || [])}${breakdown('Top 10 expense categories',data.expense_groups || [])}</div>`;
  }
  async function load() {
    const request=++sequence, form=root.querySelector('form'), status=root.querySelector('[data-status]');
    root.querySelector('[data-results]').innerHTML='';
    if(!form.elements.from.value || !form.elements.to.value || form.elements.from.value>form.elements.to.value){status.textContent='Choose a valid From and To date.';return;}
    status.textContent='Loading dashboard…';root.setAttribute('aria-busy','true');
    try {
      const params=new URLSearchParams({from_date:form.elements.from.value,to_date:form.elements.to.value,trend_days:0});
      const data=await ctx.api(`/api/dashboard/summary?${params}`);
      if(request!==sequence || root.hidden)return;
      render(data);status.textContent=`${data.period.from_date} – ${data.period.to_date} · Updated ${new Date().toLocaleTimeString()}`;
    } catch(error){if(request===sequence && !root.hidden)status.textContent=`Could not load dashboard: ${error.message}. Use Apply to retry.`;}
    finally{if(request===sequence)root.setAttribute('aria-busy','false');}
  }
  window.KayTouchDashboard={
    hide(){sequence++;if(root){root.hidden=true;root.querySelector('[data-results]').innerHTML='';root.setAttribute('aria-busy','false');}},
    show(context){
      ctx=context;
      if(!root){root=document.createElement('section');root.id='touchDashboard';root.className='touch-dashboard';document.querySelector('#app').insertBefore(root,document.querySelector('#app>footer'));}
      root.hidden=false;
      root.innerHTML=`<header class="panel dashboard-header"><div><h2>Dashboard</h2><p>Sales and expenses from your KAY POS database.</p></div><button type="button" data-sales>Back to Sales</button></header><form class="panel dashboard-filters"><label>From<input name="from" type="date" required></label><label>To<input name="to" type="date" required></label><button type="submit" class="sign-in">Apply</button><button type="button" data-period="today">Today</button><button type="button" data-period="month">This month</button></form><p data-status role="status" aria-live="polite"></p><div data-results></div>`;
      const form=root.querySelector('form');form.elements.from.value=form.elements.to.value=date(new Date());
      form.onsubmit=event=>{event.preventDefault();load();};
      root.querySelector('[data-sales]').onclick=ctx.onExit;
      root.querySelectorAll('[data-period]').forEach(button=>button.onclick=()=>{const now=new Date();form.elements.to.value=date(now);if(button.dataset.period==='month')now.setDate(1);form.elements.from.value=date(now);load();});
      load();
    }
  };
})();
