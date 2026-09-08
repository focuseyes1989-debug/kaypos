(() => {
  'use strict';
  let root, ctx, values={}, section='Appearance', generation=0, busy=false;
  const sections=['Appearance','Printer','Payment Types','Tax and Discount','Business and Branding','Receipt Text','Regional','Users'];
  const fields={
    Appearance:[['theme','Theme','select',['Light','Light Gray','Dark']],['follow_system_theme','Follow system theme','checkbox']],
    Printer:[['receipt_printer_name','App receipt printer name','text'],['receipt_paper_size','Receipt paper','select',[['0','80mm'],['1','58mm'],['2','A4']]],['receipt_print_quality','Print quality (DPI)','select',['203','300','600']],['receipt_cash_drawer_use_receipt_printer','Use receipt printer for cash drawer (App)','checkbox']],
    'Tax and Discount':[['tax_enabled','Enable tax','checkbox'],['tax_rate','Tax rate (%)','number'],['discount_enabled','Enable discount','checkbox'],['discount_type','Discount type','select',[['percentage','Percentage'],['fixed','Fixed amount'],['manual','Manual']]],['discount_value','Discount value','number']],
    'Business and Branding':[['shop_name','Business name','text'],['shop_phone','Phone','text'],['shop_address','Address','textarea'],['shop_qr_name','QR payment name','text'],['shop_logo_image','Business logo','image'],['shop_qr_code_image','Payment QR image','image']],
    'Receipt Text':[['receipt_header','Receipt header','textarea'],['receipt_footer','Receipt footer','textarea'],['shop_footer_message','Footer message','textarea'],['receipt_thank_you_text','Thank you text','text'],['show_customer_name','Show customer name','checkbox']],
    Regional:[['currency','Currency','select',['Kyats (Ks)','Dollar ($)','Baht (B)']],['language','App language','select',[['en','English'],['my','Myanmar']]]]
  };
  const notes={
    Appearance:'Shared with Kay POS App. The selected theme also applies to this Touch browser.',
    Printer:'These are shared App printer defaults. Touch uses the browser print dialog: choose the printer and matching paper there. Browser printing cannot open a cash drawer or silently select an App printer.',
    'Payment Types':'Manage payment names shared by Kay POS App, Lite and Touch.',
    'Tax and Discount':'Shared tax and discount defaults. Review the checkout totals before completing a sale.',
    'Business and Branding':'Business details and images are stored in the shared database. Upload PNG or JPEG images up to 2 MB.',
    'Receipt Text':'Receipt text shared with Kay POS App and Lite.',
    Regional:'Save the shared currency and App language. Touch interface labels currently remain in English and catalog prices are displayed in Ks.',
    Users:'Admin access is required. Leave the password blank when editing to keep the existing password.'
  };
  const esc=v=>ctx.escapeHtml(v);
  function applyTheme(settings) {
    const dark=settings.follow_system_theme==='1' ? matchMedia('(prefers-color-scheme: dark)').matches : settings.theme==='Dark';
    document.documentElement.dataset.touchTheme=dark?'dark':settings.theme==='Light Gray'?'gray':'light';
  }
  function fieldMarkup([key,label,type,options], source=values) {
    const value=source[key] ?? '';
    if(type==='checkbox')return `<label class="settings-check"><input name="${key}" type="checkbox" ${value==='1' || value===true?'checked':''}><span>${esc(label)}</span></label>`;
    if(type==='image')return `<div class="settings-image"><label>${esc(label)}<input type="file" name="${key}" accept="image/png,image/jpeg"></label><img alt="${esc(label)} preview" ${/^data:image\/(png|jpeg);base64,/.test(value)?`src="${esc(value)}"`:'hidden'}><label class="settings-check"><input type="checkbox" name="clear_${key}">Remove image</label></div>`;
    const control=type==='select'?`<select name="${key}">${options.map(o=>{const [v,l]=Array.isArray(o)?o:[o,o];return `<option value="${esc(v)}" ${String(v)===String(value)?'selected':''}>${esc(l)}</option>`;}).join('')}</select>`:type==='textarea'?`<textarea name="${key}" rows="3" maxlength="4000">${esc(value)}</textarea>`:`<input name="${key}" type="${type}" value="${esc(value)}" ${type==='number'?'min="0" step="0.01"':''} maxlength="4000">`;
    return `<label>${esc(label)}${control}</label>`;
  }
  function setBusy(on){busy=on;root.querySelectorAll('button').forEach(b=>b.disabled=on);}
  function message(text){root.querySelector('[data-settings-status]').textContent=text;}
  async function imageValue(file) {
    if(file.size>2*1024*1024 || !['image/png','image/jpeg'].includes(file.type))throw new Error('Choose a PNG or JPEG image up to 2 MB.');
    return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(new Error('Could not read image.'));reader.readAsDataURL(file);});
  }
  async function renderSection() {
    const request=++generation, panel=root.querySelector('[data-settings-panel]');
    root.querySelectorAll('[data-setting-tab]').forEach(b=>b.setAttribute('aria-current',b.dataset.settingTab===section?'page':'false'));
    panel.innerHTML=`<h2>${esc(section)}</h2><p>${esc(notes[section])}</p><p role="status" data-settings-status></p><div data-settings-content>Loading…</div>`;
    const content=panel.querySelector('[data-settings-content]');
    try {
      if(section==='Payment Types' || section==='Users') {
        const users=section==='Users', path=users?'users':'payment-types';
        const data=await ctx.api(`/api/settings/${path}`);
        if(request!==generation)return;
        const records=data[users?'users':'payment_types'] || [];
        content.innerHTML=`<button type="button" class="settings-primary" data-add>Add ${users?'user':'payment type'}</button><div class="settings-records">${records.map(r=>`<div class="settings-record"><div><strong>${esc(users?r.username:r.name)}</strong><small>${esc(users?`${r.full_name} · ${r.role} · ${r.active?'Active':'Inactive'}`:r.active?'Active':'Inactive')}</small></div><div><button type="button" data-edit="${Number(r.id)}">Edit</button><button type="button" class="settings-danger" data-delete="${Number(r.id)}">Delete</button></div></div>`).join('') || '<p>No records yet.</p>'}</div><div data-editor></div>`;
        content.querySelector('[data-add]').onclick=()=>editRecord(null,users,data.roles || []);
        content.querySelectorAll('[data-edit]').forEach(b=>b.onclick=()=>editRecord(records.find(r=>r.id===Number(b.dataset.edit)),users,data.roles || []));
        content.querySelectorAll('[data-delete]').forEach(b=>b.onclick=async()=>{
          const r=records.find(r=>r.id===Number(b.dataset.delete));
          if(busy || !confirm(`Delete ${users?r.username:r.name}?`))return;
          setBusy(true);
          try{await ctx.api(`/api/settings/${path}/${r.id}`,{method:'DELETE'});ctx.toast('Deleted.');await renderSection();}
          catch(e){message(e.message);}finally{setBusy(false);}
        });
        return;
      }
      content.innerHTML=`<form class="settings-form">${fields[section].map(f=>fieldMarkup(f)).join('')}<div class="settings-save"><button type="submit" class="settings-primary">Save ${esc(section)}</button><span>Changes are saved for all connected apps.</span></div></form>`;
      const form=content.querySelector('form');
      form.querySelectorAll('input[type=file]').forEach(input=>input.onchange=async()=>{
        try{if(input.files[0]){const img=input.closest('.settings-image').querySelector('img');img.src=await imageValue(input.files[0]);img.hidden=false;form.elements[`clear_${input.name}`].checked=false;}}
        catch(e){input.value='';message(e.message);}
      });
      form.onsubmit=async e=>{
        e.preventDefault();if(busy || !form.reportValidity())return;
        setBusy(true);message('Saving…');
        try {
          const update={};
          for(const [key,,type] of fields[section]) {
            const input=form.elements[key];
            if(type==='image') {
              if(form.elements[`clear_${key}`].checked){update[key]='';update[key==='shop_logo_image'?'shop_logo':'shop_qr_code']='';}
              else if(input.files[0]){update[key]=await imageValue(input.files[0]);update[key==='shop_logo_image'?'shop_logo':'shop_qr_code']='';}
            } else update[key]=type==='checkbox'?(input.checked?'1':'0'):input.value;
          }
          if(update.currency)update.currency_symbol={'Kyats (Ks)':'Ks','Dollar ($)':'$','Baht (B)':'B'}[update.currency];
          const data=await ctx.api('/api/settings/touch',{method:'PUT',body:JSON.stringify({settings:update})});
          values=data.settings;applyTheme(values);ctx.toast('Settings saved.');await renderSection();message('Saved successfully.');
        }catch(error){message(error.message);}finally{setBusy(false);}
      };
    }catch(error){if(request===generation){content.textContent='';message(error.message);}}
  }
  function editRecord(record,users,roles) {
    const editor=root.querySelector('[data-editor]'), data=record || {active:true,role:'Cashier'};
    const schema=users?[['username','Username','text'],['full_name','Full name','text'],['password',record?'New password (optional)':'Password','password'],['role','Role','select',roles],['active','Active account','checkbox']]:[['name','Payment type name','text']];
    editor.innerHTML=`<form class="settings-form settings-editor"><h3>${record?'Edit':'Add'} ${users?'user':'payment type'}</h3>${schema.map(f=>fieldMarkup(f,data)).join('')}<div class="settings-save"><button class="settings-primary" type="submit">Save</button><button type="button" data-cancel>Cancel</button></div></form>`;
    const form=editor.querySelector('form');form.elements[users?'username':'name'].required=true;
    if(users){form.elements.password.autocomplete='new-password';form.elements.password.required=!record;form.elements.password.maxLength=256;form.elements.username.maxLength=80;form.elements.full_name.maxLength=160;}
    else form.elements.name.maxLength=80;
    editor.querySelector('[data-cancel]').onclick=()=>{editor.innerHTML='';};
    form.onsubmit=async e=>{
      e.preventDefault();if(busy || !form.reportValidity())return;setBusy(true);message('Saving…');
      const payload={};schema.forEach(([key,,type])=>payload[key]=type==='checkbox'?form.elements[key].checked:form.elements[key].value);
      try{await ctx.api(`/api/settings/${users?'users':'payment-types'}${record?'/'+record.id:''}`,{method:record?'PUT':'POST',body:JSON.stringify(payload)});ctx.toast('Saved.');await renderSection();}
      catch(error){message(error.message);}finally{setBusy(false);}
    };
    form.elements[users?'username':'name'].focus();
    editor.scrollIntoView({behavior:'smooth',block:'nearest'});
  }
  window.KayTouchSettings={
    applyTheme,
    hide(){if(root){root.hidden=true;generation++;}},
    async show(context){
      ctx=context;
      if(!root){root=document.createElement('section');root.id='touchSettings';root.className='touch-settings';document.querySelector('#app').insertBefore(root,document.querySelector('#app>footer'));}
      root.hidden=false;
      root.innerHTML=`<header class="panel settings-heading"><div><h1>Settings</h1><p>Manage your business and shared app preferences.</p></div><button type="button" data-settings-exit>Sales</button></header><div class="settings-layout"><nav aria-label="Settings sections">${sections.map(s=>`<button type="button" data-setting-tab="${esc(s)}">${esc(s)}</button>`).join('')}</nav><section class="panel settings-panel" data-settings-panel><p>Loading settings…</p></section></div>`;
      root.querySelector('[data-settings-exit]').onclick=()=>{if(!busy)ctx.onExit();};
      root.querySelectorAll('[data-setting-tab]').forEach(b=>b.onclick=()=>{if(!busy){section=b.dataset.settingTab;renderSection();}});
      const request=++generation;
      try{const data=await ctx.api('/api/settings/touch');if(request!==generation)return;values=data.settings;applyTheme(values);await renderSection();}
      catch(error){if(request===generation)root.querySelector('[data-settings-panel]').textContent=error.message;}
    }
  };
})();
