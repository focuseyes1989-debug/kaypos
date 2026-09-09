(() => {
 'use strict';
 let root,ctx,sequence=0,offset=0,rows=[];
 const esc=v=>ctx.escapeHtml(v ?? ''),money=v=>Number(v||0).toLocaleString(undefined,{maximumFractionDigits:2});
 async function load(){
  const request=++sequence,status=root.querySelector('[data-status]');status.textContent='Loading customers…';root.querySelector('[data-rows]').innerHTML='';
  root.querySelector('[data-prev]').disabled=true;root.querySelector('[data-next]').disabled=true;
  try{
   const data=await ctx.api(`/api/customers?${new URLSearchParams({q:root.querySelector('[name=q]').value.trim(),limit:51,offset})}`);
   if(request!==sequence || root.hidden)return;
   rows=(data.customers||[]).slice(0,50);
   root.querySelector('[data-rows]').innerHTML=rows.map(r=>`<article class="customer-row"><span class="customer-avatar" aria-hidden="true">${esc(Array.from(r.name||'?')[0])}</span><div class="customer-main"><strong>${esc(r.name)}</strong><small>${esc(r.phone||'No phone')} ${r.email?' · '+esc(r.email):''}</small>${r.address?`<small>${esc(r.address)}</small>`:''}</div><div class="customer-balance"><strong>${money(r.current_balance)} Ks</strong><small>Balance · ${money(r.points)} points</small><small>Credit limit: ${money(r.credit_limit)} Ks</small></div><button type="button" data-edit="${Number(r.id)}" data-icon="edit">Edit</button></article>`).join('') || '<div class="dashboard-empty">No customers found. Add a customer or change your search.</div>';
   root.querySelectorAll('[data-edit]').forEach(b=>b.onclick=()=>edit(rows.find(r=>Number(r.id)===Number(b.dataset.edit))));
   status.textContent=rows.length?`Showing ${offset+1}–${offset+rows.length} customers`:'No matching customers';
   root.querySelector('[data-prev]').disabled=offset===0;root.querySelector('[data-next]').disabled=(data.customers||[]).length<=50;
  }catch(e){if(request===sequence && !root.hidden){status.textContent=`Could not load customers: ${e.message}. Use Search to retry.`;root.querySelector('[data-prev]').disabled=offset===0;}}
 }
 function edit(record){
  const dialog=document.createElement('dialog');dialog.className='settings-user-dialog customer-dialog';
  dialog.innerHTML=`<form><header><h2>${record?'Edit customer':'Add customer'}</h2><p>Customer details shared with KAY POS App.</p></header><div class="customer-fields">${[['name','Name','text',200],['phone','Phone','tel',100],['email','Email','email',200],['address','Address','textarea',2000],['remarks','Remarks','textarea',2000]].map(([key,label,type,max])=>`<label>${label}${type==='textarea'?`<textarea name="${key}" maxlength="${max}" rows="2">${esc(record?.[key])}</textarea>`:`<input name="${key}" type="${type}" maxlength="${max}" value="${esc(record?.[key])}" ${key==='name'?'required':''}>`}</label>`).join('')}</div><p data-error role="alert"></p><footer><button type="button" data-cancel>Cancel</button><button type="submit" class="sign-in" data-icon="save">Save customer</button></footer></form>`;
  root.appendChild(dialog);let busy=false;const form=dialog.querySelector('form');
  const close=()=>{if(!busy){dialog.close();dialog.remove();}};dialog.querySelector('[data-cancel]').onclick=close;dialog.oncancel=e=>{e.preventDefault();close();};
  form.onsubmit=async e=>{e.preventDefault();if(busy||!form.reportValidity())return;busy=true;dialog.querySelectorAll('button').forEach(b=>b.disabled=true);
   try{const values=Object.fromEntries(new FormData(form));await ctx.api(record?`/api/customers/${record.id}`:'/api/customers',{method:record?'PUT':'POST',body:JSON.stringify(values)});busy=false;close();ctx.toast('Customer saved.');await load();}
   catch(error){dialog.querySelector('[data-error]').textContent=error.message;}
   finally{busy=false;dialog.querySelectorAll('button').forEach(b=>b.disabled=false);}
  };dialog.showModal();form.elements.name.focus();
 }
 window.KayTouchCustomers={hide(){sequence++;if(root){root.hidden=true;root.querySelectorAll('dialog').forEach(d=>{d.close();d.remove();});}},show(context){ctx=context;offset=0;if(!root){root=document.createElement('section');root.id='touchCustomers';root.className='touch-dashboard touch-customers';document.querySelector('#app').insertBefore(root,document.querySelector('#app>footer'));}root.hidden=false;root.innerHTML=`<header class="panel dashboard-header"><div><h2>Customers</h2><p>Manage customer details shared with KAY POS App.</p></div><div class="customer-actions"><button data-sales type="button">Sales</button><button data-add type="button" class="sign-in" data-icon="add">Add customer</button></div></header><section class="panel customer-list"><form class="dashboard-filters"><label>Search customers<input type="search" name="q" placeholder="Customer name or phone"></label><button type="submit" class="sign-in" data-icon="search">Search</button><button type="button" data-reset>Reset</button></form><p data-status role="status"></p><div data-rows></div><div class="customer-pagination"><button type="button" data-prev>Previous</button><button type="button" data-next>Next</button></div></section>`;root.querySelector('[data-sales]').onclick=ctx.onExit;root.querySelector('[data-add]').onclick=()=>edit(null);root.querySelector('form').onsubmit=e=>{e.preventDefault();offset=0;load();};root.querySelector('[data-reset]').onclick=()=>{root.querySelector('[name=q]').value='';offset=0;load();};root.querySelector('[data-prev]').onclick=()=>{offset=Math.max(0,offset-50);load();};root.querySelector('[data-next]').onclick=()=>{offset+=50;load();};load();}};
})();
