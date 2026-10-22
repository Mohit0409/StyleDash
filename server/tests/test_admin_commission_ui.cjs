'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const original = fs.readFileSync(path.join(__dirname, '../admin/admin.js'), 'utf8');
function between(a,b){
  const i=original.indexOf(a),j=original.indexOf(b,i);
  assert.ok(i >= 0 && j>i, 'Expected admin source functions');
  return original.slice(i,j);
}
const selected=[
  between('async function editProductCommission(button){','async function editStoreProduct(button){'),
  between('async function bulkSetProductCommission(ids){','async function bulkTransition(resource){'),
  between('async function bulkTransition(resource){','const DELIVERY_ZONE_ID_PATTERN='),
  between('function bulkToolbar(resource,statuses){','function syncBulkSelectionUi(resource){'),
  between('function renderShopProducts(items,applications=shopProductStores){','function renderShopProductRequests(items){'),
].join('\n');

function product(id,pricePaise=100000,originalPricePaise=120000){
  return {
    id, name:'Fixture '+id, applicationId:'test-shop', department:'unisex',
    category:'Accessories', description:'An example product', pricePaise,
    originalPricePaise, commissionPaise:5000, customerPricePaise:105000,
    commissionBasisPoints:500, commissionOverrideBasisPoints:null,
    colourName:'Black', variants:[], status:'PUBLISHED', inventory:3,
  };
}
function fixture(config={}){
  const calls=[], notices=[];
  const products=config.products || [product('sku-one'),product('sku-two',50000,60000)];
  const content={
    innerHTML:'',querySelectorAll(){return [];}
  };
  const context={
    currentShopProducts:products,
    bulkSelection:new Set(config.ids || ['products:sku-one','products:sku-two']),
    formDialog:async (...args)=> {
      calls.push({kind:'dialog',args});
      return config.dialog;
    },
    api:async (url,opts)=>{
      calls.push({kind:'api',url,opts});
      return config.apiResponse || {updatedCount:2,selectedCount:2,unchangedCount:0};
    },
    status:(message)=>notices.push(message),
    byId:(id)=>id==='content'?content:null,
    document:{querySelector:(selector)=> {
      if(selector.startsWith('[data-bulk-target='))return {value:config.target || 'SET_COMMISSION'};
      return null;
    }},
    adminFilters:{'shop-products':{status:'all',category:'all'}},
    shopProductStores:[{id:'test-shop',shopName:'Fixture Shop'}],
    shopProductFilter:'all',
    matchesAdminSearch:()=>true,
    adminSelect:()=>'<label>Filter</label>',
    inventoryThumbnail:()=>'<span>photo</span>',
    productTransitions:()=>[],
    escapeText:(x)=>String(x??'').replace(/[&<>"']/g,(ch)=>({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;',
    }[ch])),
  };
  vm.runInNewContext(selected+'\n;globalThis.__ui={editProductCommission,bulkSetProductCommission,bulkTransition,bulkToolbar,renderShopProducts};',context);
  return {ui:context.__ui,context,calls,notices,content};
}
const apiCalls=fx=>fx.calls.filter(x=>x.kind==='api');

test('single commission updates only selected ID with private PATCH and basis points',async()=>{
  const fx=fixture({dialog:{mode:'custom',rate:'3.25'}});
  await fx.ui.editProductCommission({dataset:{id:'sku-one'}});
  assert.equal(apiCalls(fx).length,1);
  assert.equal(apiCalls(fx)[0].url,'/api/admin/shop-products/sku-one/commission');
  assert.equal(apiCalls(fx)[0].opts.method,'PATCH');
  assert.deepEqual(JSON.parse(apiCalls(fx)[0].opts.body),{commissionBasisPoints:325});
  assert.match(fx.notices[0],/3\.25%/);
});
test('single commission can restore default without overwriting MRP',async()=>{
  const fx=fixture({dialog:{mode:'default',rate:'100'}});
  await fx.ui.editProductCommission({dataset:{id:'sku-one'}});
  assert.equal(JSON.parse(apiCalls(fx)[0].opts.body).commissionBasisPoints,null);
  assert.match(fx.notices[0],/5\.00%/);
});
test('single commission cancellation, stale products and invalid rates do not send writes',async()=>{
  for(const dialog of [null,{mode:'custom',rate:'NaN'},{mode:'custom',rate:'101'},{mode:'custom',rate:'-1'},{mode:'custom',rate:'1.234'},{mode:'something',rate:'4'}]){
    const fx=fixture({dialog});
    if(dialog===null) await fx.ui.editProductCommission({dataset:{id:'sku-one'}});
    else await assert.rejects(()=>fx.ui.editProductCommission({dataset:{id:'sku-one'}}));
    assert.equal(apiCalls(fx).length,0);
  }
  const missing=fixture({dialog:{mode:'custom',rate:'5.00'}});
  await assert.rejects(()=>missing.ui.editProductCommission({dataset:{id:'missing'}}),/not found/i);
  assert.equal(apiCalls(missing).length,0);
});
test('single commission MRP guard is fail-closed',async()=>{
  const fx=fixture({dialog:{mode:'custom',rate:'10'},products:[product('sku-one',100000,105000)]});
  await assert.rejects(()=>fx.ui.editProductCommission({dataset:{id:'sku-one'}}),/MRP/);
  assert.equal(apiCalls(fx).length,0);
});
test('bulk commission sends one atomic operation for selected products',async()=>{
  const fx=fixture({dialog:{mode:'custom',rate:'2.50'}});
  const result=await fx.ui.bulkTransition('products');
  assert.equal(result,true);
  assert.equal(apiCalls(fx).length,1);
  assert.equal(apiCalls(fx)[0].url,'/api/admin/shop-products/bulk-commission');
  assert.equal(apiCalls(fx)[0].opts.method,'PATCH');
  assert.deepEqual(JSON.parse(apiCalls(fx)[0].opts.body),{
    ids:['sku-one','sku-two'],commissionBasisPoints:250,
  });
  assert.equal(fx.context.bulkSelection.size,0);
  assert.match(fx.notices[0],/2 of 2/);
});
test('bulk dialog cancellation keeps selections and does not call API',async()=>{
  const fx=fixture({dialog:null});
  assert.equal(await fx.ui.bulkTransition('products'),false);
  assert.equal(apiCalls(fx).length,0);
  assert.equal(fx.context.bulkSelection.size,2);
});
test('bulk invalid rate and MRP failures preserve all selection and avoid partial writes',async()=>{
  for(const dialog of [{mode:'custom',rate:'100.01'},{mode:'custom',rate:'3.141'},{mode:'custom',rate:''},{mode:'default-invalid',rate:'5'}]){
    const fx=fixture({dialog});
    await assert.rejects(()=>fx.ui.bulkTransition('products'));
    assert.equal(apiCalls(fx).length,0);
    assert.equal(fx.context.bulkSelection.size,2);
  }
  const mrp=fixture({
    dialog:{mode:'custom',rate:'7.00'},
    products:[product('sku-one',100000,120000),product('sku-two',50000,52000)],
  });
  await assert.rejects(()=>mrp.ui.bulkTransition('products'),/MRP/);
  assert.equal(apiCalls(mrp).length,0);
  assert.equal(mrp.context.bulkSelection.size,2);
});
test('bulk default commission passes null and preserves original MRP field',async()=>{
  const fx=fixture({dialog:{mode:'default',rate:'65.00'}});
  await fx.ui.bulkTransition('products');
  assert.equal(JSON.parse(apiCalls(fx)[0].opts.body).commissionBasisPoints,null);
});
test('private product listing visibly labels custom versus default and provides individual button',()=>{
  const custom=product('sku-one');
  custom.commissionBasisPoints=300;
  custom.commissionOverrideBasisPoints=300;
  custom.commissionPaise=3000;
  custom.customerPricePaise=103000;
  const fx=fixture({products:[custom,product('sku-two')]});
  fx.ui.renderShopProducts(fx.context.currentShopProducts,fx.context.shopProductStores);
  assert.match(fx.content.innerHTML,/Commission 3\.00% \(custom\)/);
  assert.match(fx.content.innerHTML,/Commission 5\.00% \(default\)/);
  assert.equal((fx.content.innerHTML.match(/data-action="edit-product-commission"/g)||[]).length,2);
  assert.match(fx.content.innerHTML,/data-id="sku-one">Set commission/);
});
test('bulk UI dropdown and action click wiring are present without unrelated CSV commission support',()=>{
  const fx=fixture();
  const html=fx.ui.bulkToolbar('products',['APPROVED','SET_COMMISSION']);
  assert.match(html,/value="SET_COMMISSION">Set commission/);
  assert.match(original,/if\(action==='edit-product-commission'\) await editProductCommission\(button\)/);
  assert.match(original,/addBulkControls\('products',\['UNDER_REVIEW','APPROVED','REJECTED','PUBLISHED','SET_COMMISSION'\]/);
  assert.doesNotMatch(original,/commissionPercent/);
});
