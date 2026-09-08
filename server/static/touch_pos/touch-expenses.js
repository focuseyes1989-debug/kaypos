(() => {
  'use strict';
  let root,ctx,offset=0,sequence=0,rows=[],categories=[],payments=[],busy=false;
  const esc=v=>ctx.escapeHtml(v), amount=v=>Number(v||0).toLocaleString(undefined,{minimumFractionDigits:0,maximumFractionDigits:2});
  const today=()=>{const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;};
  async function load() {
    const request=++sequence, form=root.querySelector('[data-filters]'), status=root.querySelector('[data-status]');
    if(form.elements.from.value && form.elements.to.value && form.elements.from.value>form.elements.to.value){status.textContent='From date must be before To date.';return;}
    root.querySelector('[data-rows]').innerHTML='';status.textContent='Loading expenses…';
    for(const key of ['total','count','average'])root.querySelector(`[data-${key}]`).textContent='—';
    root.querySelector('[data-prev]').disabled=true;root.querySelector('[data-next]').disabled=true;
    try{
      const query=new URLSearchParams({q:form.elements.search.value.trim(),from_date:form.elements.from.value,to_date:form.elements.to.value,limit:51,offset});
      const data=await ctx.api(`/api/expenses?${query}`);if(request!==sequence || root.hidden)return;
      rows=(data.expenses||[]).slice(0,50);
      root.querySelector('[data-total]').textContent=`${amount(data.total)} Ks`;
      const count=Number(data.total_count || 0);
      root.querySelector('[data-count]').textContent=amount(count);
      root.querySelector('[data-average]').textContent=`${amount(count?Number(data.total)/count:0)} Ks`;
      root.querySelector('[data-page]').textContent=count?`${offset+1}–${offset+rows.length} of ${amount(count)}`:'0 expenses';
      root.querySelector('[data-prev]').disabled=offset===0;root.querySelector('[data-next]').disabled=(data.expenses||[]).length<=50;
      status.textContent=rows.length?'':'No expenses match these filters.';
      root.querySelector('[data-rows]').innerHTML=rows.map(r=>`<article class="expense-entry"><div class="expense-date"><strong>${esc(String(r.expense_date).slice(8,10))}</strong><small>${esc(String(r.expense_date).slice(0,7))}</small></div><div class="expense-entry-main"><span class="expense-category">${esc(r.category)}</span><strong>${esc(r.description || r.category)}</strong><small>${esc(r.expense_no)} · ${esc(r.created_by || '—')}</small>${r.notes || r.reference_no?`<details><summary>More details</summary><p>Reference: ${esc(r.reference_no||'—')}</p><p>${esc(r.notes||'')}</p></details>`:''}</div><div class="expense-entry-amount"><strong>${amount(r.amount)} <small>Ks</small></strong><span>${esc(r.payment_method)}</span></div><div class="expense-row-actions"><button type="button" data-edit="${Number(r.id)}" aria-label="Edit ${esc(r.expense_no)}">Edit</button><button type="button" class="settings-danger" data-delete="${Number(r.id)}" aria-label="Delete ${esc(r.expense_no)}">Delete</button></div></article>`).join('') || '<div class="expense-empty"><strong>No expenses found</strong><p>Add an expense or adjust your date range and search.</p></div>';
      root.querySelectorAll('[data-delete]').forEach(b=>b.onclick=()=>remove(rows.find(r=>r.id===Number(b.dataset.delete))));
      root.querySelectorAll('[data-edit]').forEach(b=>b.onclick=()=>edit(rows.find(r=>r.id===Number(b.dataset.edit))));
    }catch(e){if(request===sequence){status.textContent=e.message;root.querySelector('[data-prev]').disabled=offset===0;}}
  }
  async function remove(record) {
    if(busy || !record)return;
    if(!confirm(`Delete ${record.expense_no}?\n${record.category} · ${amount(record.amount)} Ks\nThis permanently deletes the expense and its attachment records.`))return;
    const request=sequence;
    busy=true;root.querySelectorAll('button').forEach(b=>b.disabled=true);
    root.querySelector('[data-status]').textContent='Deleting expense…';
    try{
      await ctx.api(`/api/expenses/${Number(record.id)}`,{method:'DELETE'});
      ctx.toast('Expense deleted.');
      if(request===sequence && !root.hidden){
        if(rows.length===1 && offset>0)offset=Math.max(0,offset-50);
        root.querySelectorAll('button').forEach(b=>b.disabled=false);
        await load();
      }
    }catch(error){if(request===sequence){root.querySelector('[data-status]').textContent=error.message;root.querySelectorAll('button').forEach(b=>b.disabled=false);root.querySelector('[data-prev]').disabled=offset===0;}}
    finally{busy=false;}
  }
  async function edit(record) {
    if(busy)return;
    const request=sequence;root.querySelector('[data-status]').textContent='Loading expense form…';
    try{
      const data=await Promise.all([ctx.api('/api/expenses/categories'),ctx.api('/api/payment-types')]);
      if(request!==sequence || root.hidden)return;
      categories=data[0].categories||[];payments=data[1].payment_types||[];
      root.querySelector('[data-status]').textContent='';
    }catch(e){root.querySelector('[data-status]').textContent=e.message;return;}
    if(root.querySelector('dialog'))return;
    const r=record||{expense_date:today(),payment_method:'Cash'}, dialog=document.createElement('dialog');
    dialog.className='expense-dialog';dialog.setAttribute('aria-labelledby','expenseTitle');
    const input=(key,label,type='text')=>`<label>${label}<input name="${key}" type="${type}" value="${esc(r[key]||'')}" ${type==='date'?'required':type==='number'?'min="0.01" step="0.01" required':'maxlength="1000"'}></label>`;
    dialog.innerHTML=`<form class="expense-editor"><header><h2 id="expenseTitle">${record?'Edit expense':'Add expense'}</h2><p>Record the amount, category and payment details.</p></header><div class="settings-form expense-editor-body"><label>Category<input name="category" list="expenseCategoryOptions" value="${esc(r.category||'')}" maxlength="160" required><datalist id="expenseCategoryOptions">${categories.map(c=>`<option value="${esc(c)}"></option>`).join('')}</datalist><small>Choose an App category or enter a category name.</small></label>${input('amount','Amount (Ks)','number')}${input('expense_date','Date','date')}<label>Payment method<select name="payment_method">${[...new Set(['Cash',...payments,r.payment_method].filter(Boolean))].map(p=>`<option ${p===r.payment_method?'selected':''}>${esc(p)}</option>`).join('')}</select></label>${input('description','Description')}${input('reference_no','Reference number')}<label class="expense-wide">Notes<textarea name="notes" rows="3" maxlength="4000">${esc(r.notes||'')}</textarea></label><p class="expense-wide" role="alert" data-error></p></div><div class="settings-save"><button type="button" data-cancel>Cancel</button><button type="submit" class="settings-primary">Save expense</button></div></form>`;
    root.appendChild(dialog);const form=dialog.querySelector('form');
    dialog.querySelector('[data-cancel]').onclick=()=>{if(!busy)dialog.close();};dialog.oncancel=e=>{if(busy)e.preventDefault();};dialog.onclose=()=>dialog.remove();
    form.onsubmit=async e=>{
      e.preventDefault();if(busy || !form.reportValidity())return;
      const payload=Object.fromEntries(new FormData(form));payload.category=payload.category.trim();payload.amount=Number(payload.amount);
      if(!payload.category || !Number.isFinite(payload.amount) || payload.amount<=0){dialog.querySelector('[data-error]').textContent='Enter a category and an amount greater than zero.';return;}
      busy=true;dialog.querySelectorAll('button').forEach(b=>b.disabled=true);
      try{
        await ctx.api(`/api/expenses${record?'/'+record.id:''}`,{method:record?'PUT':'POST',body:JSON.stringify(payload)});
        ctx.toast(record?'Expense updated.':'Expense saved.');dialog.close();await load();
      }catch(error){dialog.querySelector('[data-error]').textContent=error.message;}
      finally{busy=false;dialog.querySelectorAll('button').forEach(b=>b.disabled=false);}
    };
    dialog.showModal();
  }
  window.KayTouchExpenses={
    hide(){sequence++;if(root){root.hidden=true;root.querySelector('dialog')?.close();}},
    show(context){
      ctx=context;offset=0;
      if(!root){root=document.createElement('section');root.id='touchExpenses';root.className='touch-settings touch-expenses';document.querySelector('#app').insertBefore(root,document.querySelector('#app>footer'));}
      root.hidden=false;
      root.innerHTML=`<header class="panel settings-heading"><div><h1>Expenses</h1><p>Review spending and keep your expense records up to date.</p></div><div class="expense-head-actions"><button type="button" data-sales>Sales</button><button type="button" class="settings-primary" data-add>+ Add expense</button></div></header><div class="expense-metrics"><div class="panel expense-metric"><small>Total spending</small><strong data-total>—</strong><span>Matching your filters</span></div><div class="panel expense-metric"><small>Expenses</small><strong data-count>—</strong><span>Matching records</span></div><div class="panel expense-metric"><small>Average expense</small><strong data-average>—</strong><span>Per matching record</span></div></div><section class="panel expense-ledger"><div class="expense-ledger-heading"><h2>Expense history</h2><div class="expense-presets"><button type="button" data-period="today">Today</button><button type="button" data-period="month">This month</button><button type="button" data-period="all">All time</button></div></div><form class="expense-filters settings-form" data-filters><label>From<input type="date" name="from"></label><label>To<input type="date" name="to"></label><label>Search<input type="search" name="search" maxlength="200" placeholder="Category, description or reference"></label><div class="expense-filter-actions"><button type="submit" class="settings-primary">Apply</button><button type="button" data-reset>Reset</button></div></form><p role="status" data-status></p><div data-rows></div><div class="expense-pagination"><button data-prev type="button">Previous</button><span data-page></span><button data-next type="button">Next</button></div></section>`;
      const filter=root.querySelector('[data-filters]');
      root.querySelectorAll('[data-period]').forEach(button=>button.onclick=()=>{
        const date=today(), period=button.dataset.period;
        filter.elements.from.value=period==='today'?date:period==='month'?date.slice(0,8)+'01':'';
        filter.elements.to.value=period==='all'?'':date;offset=0;load();
      });
      root.querySelector('[data-reset]').onclick=()=>{filter.reset();offset=0;load();};
      root.querySelector('[data-sales]').onclick=ctx.onExit;root.querySelector('[data-add]').onclick=()=>edit(null);
      root.querySelector('[data-filters]').onsubmit=e=>{e.preventDefault();offset=0;load();};
      root.querySelector('[data-prev]').onclick=()=>{offset=Math.max(0,offset-50);load();};root.querySelector('[data-next]').onclick=()=>{offset+=50;load();};load();
    }
  };
})();
