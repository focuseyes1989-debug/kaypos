const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const src=fs.readFileSync('server/static/touch_pos/touch-settings.js','utf8').replace('    applyTheme,','    applyTheme,saveAppearance,appearanceSettings,');
function browser(){const data=new Map(),events={},media={matches:false,addEventListener:(k,f)=>events.system=f};const c={window:{matchMedia:()=>media,addEventListener:(k,f)=>events[k]=f},localStorage:{getItem:k=>data.get(k),setItem:(k,v)=>data.set(k,v)},document:{documentElement:{dataset:{}}}};vm.createContext(c);vm.runInContext(src,c);return {api:c.window.KayTouchSettings,theme:()=>c.document.documentElement.dataset.touchTheme,data,media,events};}
const a=browser(),b=browser();a.api.saveAppearance({theme:'Dark'});assert.equal(a.theme(),'dark');assert.equal(b.theme(),'light');a.api.applyTheme({theme:'Light'});assert.equal(a.theme(),'dark');
a.api.saveAppearance({theme:'Light Gray',follow_system_theme:'1'});assert.equal(a.theme(),'light');a.media.matches=true;a.events.system();assert.equal(a.theme(),'dark');
a.api.saveAppearance({theme:'Light Gray',follow_system_theme:'0'});a.events.system();assert.equal(a.theme(),'gray');
a.data.set('kay.touch.appearance.v1','broken');a.events.storage({key:'kay.touch.appearance.v1'});assert.equal(a.theme(),'light');
assert.match(src,/if\(section==='Appearance'\) \{[\s\S]*?saveAppearance\(update\)[\s\S]*?return;/);
console.log('Local themes: device isolation, shared-setting override ignored, system changes, gray and invalid storage passed.');
