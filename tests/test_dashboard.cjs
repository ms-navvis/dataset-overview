// Logic checks using a minimal DOM. This is not a browser/layout test.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const html=fs.readFileSync(path.join(__dirname,'../navvis_dataset_explorer/dashboard.html'),'utf8');
const script=[...html.matchAll(/<script([^>]*)>([\s\S]*?)<\/script>/g)][1][2];
const rows=Array.from({length:251},(_,i)=>({path:`collection/${i}/dataset.json`,collection:'collection',folder_path:`/demo/${i}`,logical_bytes:(i+1)*1e9,allocated_bytes:(i+1)*1e9,file_count:2,size_complete:true,metadata:{dataset:{name:`Synthetic ${String(i).padStart(3,'0')}`,dataset_id:`demo-${i}`},device:{serial:i===0?'G11-0000':'L4-0000'},statistics:{mapping_timestart:1700000000+i,mapping_duration:60,capture_locations_panoramas_rec:1,mapped_area_v2_rec:20}}}));
function setup(datasets){const inventory={summary:{drive:'/demo',label:'Demo',scan_time_utc:'2026-01-01T00:00:00Z',errors:[]},datasets};const elements=new Map();function element(id){if(!elements.has(id))elements.set(id,{value:'',textContent:'',innerHTML:'',events:{},add(){},addEventListener(name,fn){this.events[name]=fn;}});return elements.get(id);}element('inventory').textContent=JSON.stringify(inventory);const heads=['name','collection','date','size','allocated','duration','area','captures','model','serial'].map(key=>({dataset:{key},button:{textContent:key,dataset:{},addEventListener(name,fn){this[name]=fn;}},setAttribute(){},querySelector(){return this.button;}}));const context={document:{getElementById:element,querySelectorAll:()=>heads,querySelector:()=>({focus(){}})},Intl,Option:function(){},Blob,URL,setTimeout};vm.createContext(context);vm.runInContext(script,context);return {element,heads,context};}
let {element,heads,context}=setup(rows);
assert.equal(element('count').textContent,251);
assert.equal((element('rows').innerHTML.match(/class="data"/g)||[]).length,100);
assert.ok(element('page-status').textContent.includes('1–100'));
element('next').events.click();assert.ok(element('page-status').textContent.includes('101–200'));
element('next').events.click();assert.equal((element('rows').innerHTML.match(/class="data"/g)||[]).length,51);
assert.equal(element('next').disabled,true);
element('model').value='VLX 3';element('model').events.change();assert.equal(element('count').textContent,1);assert.ok(element('rows').innerHTML.includes('G11-0000'));
element('device').value='L4-0000';element('device').events.change();assert.equal(element('count').textContent,0);
element('reset').events.click();assert.equal(element('count').textContent,251);
element('search').value='vlx 3';element('search').events.input();assert.equal(element('count').textContent,1);
element('rows').events.click({target:{closest:()=>({dataset:{detail:'0'}})}});assert.ok(element('rows').innerHTML.includes('capture_locations_panoramas_rec'));
element('reset').events.click();heads[0].button.click();assert.ok(element('rows').innerHTML.includes('Synthetic 000'));assert.ok(!element('rows').innerHTML.includes('Synthetic 250'));
assert.equal(vm.runInContext("modelFor('G12-0001')",context),'VLX 4');assert.equal(vm.runInContext("modelFor('K4-0001')",context),'MLX');
({element}=setup([{path:'missing/dataset.json',folder_path:'/demo/missing',logical_bytes:10,allocated_bytes:null,file_count:1,metadata:{dataset:null,statistics:null,device:null}}]));
assert.equal(element('allocated').textContent,'Unavailable');assert.equal(element('duration').textContent,'Unavailable');assert.ok(element('rows').innerHTML.includes('Unknown'));
({element}=setup([{...rows[0],path:'parent/dataset.json',logical_bytes:10e9,allocated_bytes:10e9},{...rows[1],path:'parent/child/dataset.json',logical_bytes:5e9,allocated_bytes:5e9}]));
assert.equal(element('size').textContent,'10.00 GB');assert.equal(element('count').textContent,2);
({element}=setup([{...rows[0],logical_bytes:null,allocated_bytes:null}]));assert.equal(element('size').textContent,'Not measured');
({element}=setup([]));assert.equal(element('count').textContent,0);assert.ok(element('rows').innerHTML.includes('No datasets match'));
console.log('Dashboard checks passed: pagination, filters, sorting, search, metadata expansion, mappings, missing metadata, nested sizes, and empty state.');
