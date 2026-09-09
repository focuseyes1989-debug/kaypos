(() => {
  'use strict';
  const storageKey='kay.touch.local-printer.v1';
  const defaults={receipt_printer_name:'',receipt_paper_size:'0',receipt_print_quality:'203',touch_auto_print_receipt:'0',touch_auto_open_drawer:'0',bridge_key:''};
  function settings(){try{return {...defaults,...JSON.parse(localStorage.getItem(storageKey)||'{}')};}catch{return {...defaults};}}
  function save(values){localStorage.setItem(storageKey,JSON.stringify({...defaults,...values}));}
  async function request(path, payload, config=settings()) {
    if(!config.bridge_key)throw new Error('Start the Local Print Bridge and enter its pairing key in Printer settings.');
    const controller=new AbortController(), timeout=setTimeout(()=>controller.abort(),55000);
    try {
      const response=await fetch(`http://127.0.0.1:17861${path}`,{method:payload?'POST':'GET',headers:{'Content-Type':'application/json','X-Kay-Bridge-Key':config.bridge_key},body:payload?JSON.stringify(payload):undefined,signal:controller.signal,credentials:'omit',cache:'no-store',targetAddressSpace:'loopback'});
      const result=await response.json();
      if(!response.ok)throw new Error(result.error || 'Local printer request failed');
      return result;
    }catch(error){
      if(error.name==='AbortError')throw new Error('Local printer timed out. Check the print queue before retrying.');
      if(error instanceof TypeError)throw new Error('Local bridge is not reachable. Start it on this PC, check the Touch website address, and allow local network access if Chrome asks.');
      throw error;
    }finally{clearTimeout(timeout);}
  }
  function jobKey(){return crypto.randomUUID();}
  function paper(config){return {'0':'80','1':'58','2':'a4'}[config.receipt_paper_size] || '80';}
  async function print(receipt, paid, size, key=jobKey(), config=settings()){
    if(!config.receipt_printer_name)throw new Error('Select and save a local printer in Printer settings.');
    return request('/print',{request_key:key,printer:config.receipt_printer_name,receipt,paid,dpi:config.receipt_print_quality,paper:size || paper(config)},config);
  }
  async function drawer(key=jobKey(),config=settings()){
    if(!config.receipt_printer_name)throw new Error('Select and save a local printer in Printer settings.');
    return request('/drawer',{request_key:key,printer:config.receipt_printer_name},config);
  }
  window.KayLocalPrinter={settings,save,print,drawer,jobKey,paper,printers:config=>request('/printers',null,config)};
})();
