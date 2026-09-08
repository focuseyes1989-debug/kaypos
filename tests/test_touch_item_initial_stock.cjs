const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('server/static/touch_pos/touch-pos.js','utf8');
const fields={}; for(const id of ['itemSoldBy','itemName','itemCategory','itemDescription','itemPrice','itemCost','itemStock','itemLowStock','itemSku','itemBarcode','itemUnit','itemPackUnit','itemPackSize']) fields['#'+id]={value:'',disabled:false, label:{hidden:false},closest(){return this.label;}};
Object.assign(fields['#itemSoldBy'],{value:'Each'});fields['#itemCost'].value='900';fields['#itemStock'].value='12';
const c={editingProduct:null,document:{querySelector:s=>fields[s],getElementById:id=>fields['#'+id],querySelectorAll:()=>[]},soldByMode:s=>s.toLowerCase(),readItemRows:s=>s==='#itemVariants'?[{color:'Red',price:1000,cost:900,stock:12}]:[]};
vm.createContext(c);vm.runInContext(source.slice(source.indexOf('  function itemPayload()'),source.indexOf('  async function saveItemForm')),c);vm.runInContext(source.slice(source.indexOf('  function updateItemMode()'),source.indexOf('  function previewItemImage()')),c);
for(const mode of ['Each','Variants','Service']){fields['#itemSoldBy'].value=mode;c.updateItemMode();assert.equal(fields['#itemCost'].label.hidden,true);assert.equal(fields['#itemStock'].label.hidden,true);const p=c.itemPayload();assert.equal(p.cost,0);assert.equal(p.stock,0);for(const v of p.variants){assert.equal(v.cost,0);assert.equal(v.stock,0);}}
c.editingProduct={id:1};fields['#itemSoldBy'].value='Each';c.updateItemMode();assert.equal(fields['#itemCost'].label.hidden,true);assert.equal(fields['#itemStock'].label.hidden,true);assert.equal(c.itemPayload().cost,900);assert.equal(c.itemPayload().stock,12);
fields['#itemSoldBy'].value='Variants'; const edited=c.itemPayload(); assert.equal(edited.variants[0].cost,900); assert.equal(edited.variants[0].stock,12);
console.log('Add Item zero stock/cost and Edit preservation checks passed');
