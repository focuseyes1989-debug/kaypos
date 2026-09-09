(() => {
  'use strict';
  let root, ctx, sequence = 0;
  const date = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  const money = n => Number(n || 0).toLocaleString(undefined, {maximumFractionDigits:2});
  function breakdownTabs(data, kind) {
    const tabs = kind === 'sales' ? [['Items','top_items'],['Categories','category_sales'],['Parent','parent_sales'],['Payment','payment_sales'],['Wholesale','wholesale_sales'],['Discount','discount_sales']] : [['Items','expense_items'],['Categories','expense_groups']];
    return `<section class="panel dashboard-breakdown" data-breakdown="${kind}"><h3>${kind === 'sales' ? 'Sale by' : 'Expense by'}</h3><nav class="dashboard-tabs" aria-label="${kind} breakdown">${tabs.map(([label,key],i)=>`<button type="button" data-breakdown-key="${key}" aria-pressed="${i===0}">${label}</button>`).join('')}</nav><div data-breakdown-content></div></section>`;
  }
  function fillBreakdown(panel, data, key) {
    const rows=data[key] || [];
    const note=key==='discount_sales' ? 'Top 10 discounted receipts · Amount is the discount, not sale revenue.' : key==='wholesale_sales' ? 'Top 10 items sold using a recorded wholesale tier.' : key==='expense_items' ? 'Top 10 expense descriptions, grouped by name.' : key==='payment_sales' ? 'Completed sales by payment type.' : 'Top 10 by amount · Item totals are before receipt-level discount and tax.';
    const content=panel.querySelector('[data-breakdown-content]');
    content.innerHTML=`<p class="dashboard-breakdown-note">${key==='expense_groups'?'Top 10 expense categories by amount.':note}</p>${rows.length ? rows.map(r=>`<article class="dashboard-breakdown-row"><span class="dashboard-row-icon" aria-hidden="true"><img src="/assets/icons/receipt.svg" alt=""></span><span class="dashboard-row-main">${ctx.escapeHtml(r.label)}<small>${r.qty!==undefined ? `${money(r.qty)} units` : r.discount!==undefined ? `Sale total: ${money(r.total)} Ks` : `${money(r.count)} records`}</small></span><strong>${money(r.discount!==undefined?r.discount:r.total)} Ks</strong></article>`).join('') : `<p>${key==='wholesale_sales' && data.wholesale_available===false ? 'Wholesale history is not available in this database.' : 'No records for this period.'}</p>`}`;
    panel.querySelectorAll('[data-breakdown-key]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.breakdownKey===key)));
  }
  function creditPanel(data) {
    const credit=data.credit_summary || {}, rows=data.credit_accounts || [];
    return `<section class="panel dashboard-credit"><header><div><h3>Outstanding customers</h3><p>Current balances across all dates · Top 10 customers</p></div><span class="dashboard-badge">${money(credit.overdue)} overdue accounts</span></header>${rows.length ? rows.map(r=>`<article class="dashboard-breakdown-row"><span class="dashboard-row-icon" aria-hidden="true"><img src="/assets/icons/groups.svg" alt=""></span><span class="dashboard-row-main"><strong>${ctx.escapeHtml(r.label)}</strong><small>${money(r.count)} credit accounts${r.due_date?` · Earliest due: ${ctx.escapeHtml(r.due_date)}`:''}</small></span><span class="dashboard-row-amount"><strong>${money(r.balance)} Ks</strong><small>Outstanding</small></span></article>`).join('') : '<div class="dashboard-empty">No outstanding customer balances.</div>'}</section>`;
  }
  function render(data) {
    const p=data.period || {}, e=data.expenses || {}, c=data.credit_summary || {}, metrics=data.dashboard_metrics || {};
    const cards=[['Sales',p.sales,`${money(p.transactions)} completed sales`,'sales'],['Expenses',e.total,`${money(e.count)} expense records`,'expense'],['Discount',metrics.discounts,'Discounts on completed sales','discount'],['Sales less expenses',Number(p.sales||0)-Number(e.total||0),'Before cost of goods; not net profit','balance']];
    const card=([label,value,note,tone])=>`<article class="panel dashboard-metric" data-tone="${tone}"><div><span>${label}</span><small>${note}</small></div><strong>${money(value)} <small>Ks</small></strong></article>`;
    root.querySelector('[data-results]').innerHTML=`<div class="dashboard-section-title"><h3>Period overview</h3><span>${ctx.escapeHtml(p.from_date || '')} – ${ctx.escapeHtml(p.to_date || '')}</span></div><div class="dashboard-cards">${cards.map(card).join('')}</div><section class="panel dashboard-summary"><h3>Sales summary</h3><div><span>Sales including refunded receipts</span><strong>${money(p.gross_sales)} Ks</strong></div><div><span>Refunded receipts</span><strong>${money(p.refunds)} Ks</strong></div><div><span>Average completed sale</span><strong>${money(p.transactions ? p.sales/p.transactions : 0)} Ks</strong></div><small>Sales use the receipt date; expenses use the expense date. Refunded receipts are excluded from completed sales.</small></section><div class="dashboard-columns">${breakdownTabs(data,'sales')}${breakdownTabs(data,'expenses')}</div><div class="dashboard-section-title"><h3>Credit & outstanding</h3><span>All dates · Current balances</span></div><div class="dashboard-cards dashboard-credit-cards">${[['Credit issued',c.total,`${money(c.accounts)} non-cancelled credit accounts`,'credit'],['Credit paid',c.paid,'Payments recorded against credit accounts','sales'],['Outstanding',c.balance,'Remaining customer credit balance','discount']].map(card).join('')}</div>${creditPanel(data)}`;
    root.querySelectorAll('[data-breakdown]').forEach(panel=>{
      const buttons=panel.querySelectorAll('[data-breakdown-key]');
      fillBreakdown(panel,data,buttons[0].dataset.breakdownKey);
      buttons.forEach(button=>button.onclick=()=>fillBreakdown(panel,data,button.dataset.breakdownKey));
    });
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
      root.innerHTML=`<header class="panel dashboard-header"><div><h2>Dashboard</h2><p>Review sales, expenses and customer credit in one place.</p></div><button type="button" data-sales>Back to Sales</button></header><form class="panel dashboard-filters"><label>From<input name="from" type="date" required></label><label>To<input name="to" type="date" required></label><button type="submit" class="sign-in" data-icon="check_circle">Apply</button><button type="button" data-period="today">Today</button><button type="button" data-period="month">This month</button></form><p data-status role="status" aria-live="polite"></p><div data-results></div>`;
      const form=root.querySelector('form');form.elements.from.value=form.elements.to.value=date(new Date());
      form.onsubmit=event=>{event.preventDefault();load();};
      root.querySelector('[data-sales]').onclick=ctx.onExit;
      root.querySelectorAll('[data-period]').forEach(button=>button.onclick=()=>{const now=new Date();form.elements.to.value=date(now);if(button.dataset.period==='month')now.setDate(1);form.elements.from.value=date(now);load();});
      load();
    }
  };
})();
