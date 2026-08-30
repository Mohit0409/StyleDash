let csrfToken = '';
let activeTab = 'orders';
let currentOrders = [];
let orderFilters = {status:'all', payment:'all', fulfillment:'all'};

const byId = id => document.getElementById(id);
const escapeText = value => String(value ?? '').replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body) headers.set('Content-Type', 'application/json');
  if (!['GET', 'HEAD'].includes((options.method || 'GET').toUpperCase()) && csrfToken) headers.set('X-CSRF-Token', csrfToken);
  const response = await fetch(path, {...options, headers, credentials:'include'});
  const payload = await response.json().catch(() => ({error:'Invalid local service response.'}));
  if (!response.ok) throw new Error(payload.error || 'Administrator request failed.');
  return payload;
}

function showLogin() { byId('login-view').hidden = false; byId('app-view').hidden = true; csrfToken = ''; }
function showApp(admin) { byId('login-view').hidden = true; byId('app-view').hidden = false; byId('admin-name').textContent = admin.username; loadTab(activeTab); }
function error(message, target='app-error') { byId(target).textContent = message || ''; }

byId('password-form').addEventListener('submit', async event => {
  event.preventDefault(); error('', 'auth-error');
  try {
    await api('/api/admin/login', {method:'POST', body:JSON.stringify({username:byId('username').value,password:byId('password').value})});
    byId('password-form').hidden = true; byId('totp-form').hidden = false; byId('totp').focus();
  } catch (cause) { error(cause.message, 'auth-error'); }
});

byId('totp-form').addEventListener('submit', async event => {
  event.preventDefault(); error('', 'auth-error');
  try { const result=await api('/api/admin/totp',{method:'POST',body:JSON.stringify({code:byId('totp').value})}); csrfToken=result.csrfToken; showApp(result.admin); }
  catch (cause) { error(cause.message, 'auth-error'); }
});

byId('logout').addEventListener('click', async () => { try { await api('/api/admin/logout',{method:'POST',body:'{}'}); } finally { location.reload(); } });
byId('tabs').addEventListener('click', event => { const button=event.target.closest('[data-tab]'); if(!button)return; activeTab=button.dataset.tab; document.querySelectorAll('[data-tab]').forEach(item=>item.classList.toggle('active',item===button)); loadTab(activeTab); });
byId('search-form').addEventListener('submit', event => { event.preventDefault(); loadTab(activeTab); });
byId('content').addEventListener('change', event => { const control=event.target.closest('[data-order-filter]'); if(!control)return; orderFilters[control.dataset.orderFilter]=control.value; renderOrdersView(); });

function status(message) { byId('app-status').textContent = message || ''; }
function formDialog(title, fields, submitLabel='Continue') {
  return new Promise(resolve => {
    const dialog=byId('admin-dialog');
    const form=byId('admin-dialog-form');
    const fieldsRoot=byId('admin-dialog-fields');
    byId('admin-dialog-title').textContent=title;
    byId('admin-dialog-submit').textContent=submitLabel;
    byId('admin-dialog-error').textContent='';
    fieldsRoot.replaceChildren();
    for(const field of fields){
      const label=document.createElement('label'); label.textContent=field.label;
      const control=field.type==='textarea'?document.createElement('textarea'):document.createElement('input');
      control.name=field.name; control.value=field.value??''; control.required=field.required===true;
      if(field.type&&field.type!=='textarea')control.type=field.type;
      if(field.placeholder)control.placeholder=field.placeholder;
      if(field.minLength)control.minLength=field.minLength;
      if(field.maxLength)control.maxLength=field.maxLength;
      if(field.min!==undefined)control.min=String(field.min);
      if(field.max!==undefined)control.max=String(field.max);
      if(field.step!==undefined)control.step=String(field.step);
      label.appendChild(control); fieldsRoot.appendChild(label);
    }
    let settled=false;
    const finish=value=>{if(settled)return;settled=true;form.onsubmit=null;byId('admin-dialog-cancel').onclick=null;dialog.oncancel=null;if(dialog.open)dialog.close();resolve(value);};
    form.onsubmit=event=>{event.preventDefault();if(!form.reportValidity())return;finish(Object.fromEntries(new FormData(form).entries()));};
    byId('admin-dialog-cancel').onclick=()=>finish(null);
    dialog.oncancel=event=>{event.preventDefault();finish(null);};
    dialog.showModal();
    fieldsRoot.querySelector('input,textarea')?.focus();
  });
}
function parseVariants(raw) {
  const rows=String(raw||'').split(',').map(value=>value.trim()).filter(Boolean).map(value=>{
    const split=value.lastIndexOf(':');
    if(split<=0)throw new Error('Use size:stock format, for example S:5, M:8, L:2.');
    const size=value.slice(0,split).trim(); const inventory=Number(value.slice(split+1).trim());
    if(!size||!Number.isInteger(inventory)||inventory<0||inventory>100000)throw new Error('Each size needs a valid whole-number stock.');
    return {size,inventory};
  });
  if(!rows.length)throw new Error('Add at least one size and stock row.');
  return rows;
}
async function createOwnerAccount(){
  const values=await formDialog('Create store owner account',[
    {name:'name',label:'Store owner full name',required:true,maxLength:80},
    {name:'phone',label:'Mobile number (required; used for OTP login)',required:true,maxLength:20},
    {name:'email',label:'Store owner email (optional)',type:'email',maxLength:254},
    {name:'password',label:'Temporary password (8+ characters; email login if provided)',type:'password',required:true,minLength:8,maxLength:256},
  ],'Create owner account'); if(!values)return;
  await api('/api/admin/customers',{method:'POST',body:JSON.stringify({name:values.name,email:values.email||undefined,phone:values.phone,password:values.password})});
  status(`Owner account created for ${values.phone}. Mobile OTP login is ready${values.email?'; email/password login is also available.':'.'}`);
}
async function resetCustomerPassword(userId){
  const values=await formDialog('Reset customer password',[{name:'password',label:'New temporary password (8+ characters)',type:'password',required:true,minLength:8,maxLength:256}],'Reset password'); if(!values)return;
  await api(`/api/admin/customers/${encodeURIComponent(userId)}/password`,{method:'PATCH',body:JSON.stringify({password:values.password})});
  status('Temporary password updated. Existing sessions were signed out.');
}
async function createLocalStore(){
  const values=await formDialog('Create local store',[
    {name:'ownerUserId',label:'Owner customer ID',required:true,maxLength:128},
    {name:'shopName',label:'Store name',required:true,maxLength:100},
    {name:'ownerName',label:'Owner name',required:true,maxLength:80},
    {name:'category',label:'Category',required:true,value:'Clothing & Fashion',maxLength:80},
    {name:'description',label:'Store description',type:'textarea',required:true,maxLength:1000},
    {name:'address',label:'Store address',type:'textarea',required:true,maxLength:250},
    {name:'city',label:'City',required:true,value:'Neemuch',maxLength:80},
    {name:'state',label:'State',required:true,value:'Madhya Pradesh',maxLength:80},
    {name:'pincode',label:'Pincode',required:true,value:'458441',maxLength:6},
    {name:'businessInformation',label:'Business information (optional)',type:'textarea',maxLength:1000},
  ],'Create and activate store'); if(!values)return;
  await api('/api/admin/vendors',{method:'POST',body:JSON.stringify(values)});
  status(`${values.shopName} created and activated.`);
}
async function createStoreProduct(){
  const values=await formDialog('Add product for local store',[
    {name:'applicationId',label:'Store application ID',required:true,maxLength:128},
    {name:'name',label:'Product name',required:true,maxLength:140},
    {name:'description',label:'Product description',type:'textarea',required:true,maxLength:2000},
    {name:'brand',label:'Brand (optional)',maxLength:100},
    {name:'department',label:'Department',required:true,value:'unisex',placeholder:'men, women, kids, unisex, footwear, accessories'},
    {name:'category',label:'Category',required:true,value:'Clothing & Fashion'},
    {name:'price',label:'Selling price in rupees',type:'number',required:true,min:1,step:'0.01'},
    {name:'originalPrice',label:'Original/MRP price in rupees',type:'number',min:1,step:'0.01'},
    {name:'variants',label:'Sizes and stock (S:5, M:8, L:3)',required:true,placeholder:'S:5, M:8, L:3'},
    {name:'colourName',label:'Colour name',required:true,value:'Multi'},
    {name:'colourHex',label:'Colour hex (optional)',placeholder:'#000000'},
    {name:'images',label:'HTTPS image URLs separated by commas',type:'textarea',required:true},
  ],'Publish product'); if(!values)return;
  const price=Number(values.price); const originalPrice=Number(values.originalPrice||values.price);
  if(!Number.isFinite(price)||price<1||!Number.isFinite(originalPrice)||originalPrice<price)throw new Error('Enter valid selling and original prices.');
  const variants=parseVariants(values.variants);
  const imageUrls=values.images.split(',').map(value=>value.trim()).filter(Boolean);
  const payload={applicationId:values.applicationId,name:values.name,description:values.description,brand:values.brand||undefined,department:values.department,category:values.category,pricePaise:Math.round(price*100),originalPricePaise:Math.round(originalPrice*100),variants,colourName:values.colourName,colourHex:values.colourHex||undefined,imageUrls,attributes:{}};
  await api('/api/admin/shop-products',{method:'POST',body:JSON.stringify(payload)});
  status(`${values.name} published for the selected local store.`);
}
async function editStoreProduct(button){
  const values=await formDialog('Edit product details',[
    {name:'name',label:'Product name',required:true,value:button.dataset.name||'',maxLength:140},
    {name:'description',label:'Description',type:'textarea',required:true,value:button.dataset.description||'',maxLength:2000},
    {name:'price',label:'Selling price in rupees',type:'number',required:true,value:button.dataset.price||'',min:1,step:'0.01'},
    {name:'original',label:'Original/MRP price in rupees',type:'number',required:true,value:button.dataset.original||button.dataset.price||'',min:1,step:'0.01'},
  ],'Save details'); if(!values)return;
  const price=Number(values.price); const original=Number(values.original);
  if(!Number.isFinite(price)||price<1||!Number.isFinite(original)||original<price)throw new Error('Enter valid selling and original prices.');
  const payload={name:values.name,description:values.description,pricePaise:Math.round(price*100),originalPricePaise:Math.round(original*100)};
  await api(`/api/admin/shop-products/${encodeURIComponent(button.dataset.id)}/details`,{method:'PATCH',body:JSON.stringify(payload)});
  status('Product details updated.');
}
async function reasonFor(title){const values=await formDialog(title,[{name:'reason',label:'Reason',type:'textarea',required:true,maxLength:1000}],'Continue');return values?.reason||null;}
async function inventoryAdjustment(){const values=await formDialog('Adjust inventory',[{name:'delta',label:'Stock adjustment (for example 5 or -2)',type:'number',required:true,step:'1'}],'Apply adjustment');if(!values)return null;const delta=Number(values.delta);if(!Number.isSafeInteger(delta))throw new Error('Enter a whole-number stock adjustment.');return delta;}
byId('content').addEventListener('click', async event => {
  const button=event.target.closest('[data-action]'); if(!button)return;
  button.disabled=true; error(''); status('');
  try {
    const action=button.dataset.action;
    if(action==='clear-order-filters'){orderFilters={status:'all',payment:'all',fulfillment:'all'};renderOrdersView();return;}
    if(action==='create-owner') await createOwnerAccount();
    if(action==='reset-customer-password') await resetCustomerPassword(button.dataset.id);
    if(action==='create-store') await createLocalStore();
    if(action==='create-shop-product') await createStoreProduct();
    if(action==='edit-shop-product') await editStoreProduct(button);
    if(action==='order-status') await api(`/api/admin/orders/${encodeURIComponent(button.dataset.id)}/status`,{method:'PATCH',body:JSON.stringify({status:button.dataset.value})});
    if(action==='vendor') { const nextStatus=button.dataset.value; let reason=null; if(['REJECTED','SUSPENDED'].includes(nextStatus)){reason=await reasonFor(`Enter the ${nextStatus.toLowerCase()} reason`);if(!reason)return;} await api(`/api/admin/vendors/${encodeURIComponent(button.dataset.id)}`,{method:'PATCH',body:JSON.stringify({status:nextStatus,reason})}); status('Shop application status updated.'); }
    if(action==='shop-product') { const nextStatus=button.dataset.value; let reason=null; if(nextStatus==='REJECTED'){reason=await reasonFor('Enter the product rejection reason');if(!reason)return;} await api(`/api/admin/shop-products/${encodeURIComponent(button.dataset.id)}`,{method:'PATCH',body:JSON.stringify({status:nextStatus,reason})}); status('Shop product status updated.'); }
    if(action==='shop-product-request') { const nextStatus=button.dataset.value; let reason=null; if(nextStatus==='REJECTED'){reason=await reasonFor('Enter the product-request rejection reason');if(!reason)return;} await api(`/api/admin/shop-product-requests/${encodeURIComponent(button.dataset.id)}`,{method:'PATCH',body:JSON.stringify({status:nextStatus,reason})}); status('Product request status updated.'); }
    if(action==='inventory') { const delta=await inventoryAdjustment(); if(delta===null)return; await api(`/api/admin/inventory/${encodeURIComponent(button.dataset.id)}`,{method:'PATCH',body:JSON.stringify({delta})}); status('Inventory adjustment saved.'); }
    if(action==='customer') await api(`/api/admin/customers/${encodeURIComponent(button.dataset.id)}`,{method:'PATCH',body:JSON.stringify({active:button.dataset.value==='true'})});
    await loadTab(activeTab);
  } catch(cause){error(cause.message);} finally{button.disabled=false;}
});

async function loadTab(tab) {
  error(''); byId('content').innerHTML='<p>Loading…</p>';
  try {
    const query=encodeURIComponent(byId('search').value.trim());
    byId('search-form').hidden=!['orders','inventory','customers'].includes(tab);
    if(tab==='orders') return renderOrders((await api(`/api/admin/orders?q=${query}`)).orders);
    if(tab==='vendors') return renderVendors((await api('/api/admin/vendors')).applications);
    if(tab==='shop-products') return renderShopProducts((await api('/api/admin/shop-products')).products);
    if(tab==='shop-product-requests') return renderShopProductRequests((await api('/api/admin/shop-product-requests')).requests);
    if(tab==='inventory') return renderInventory((await api(`/api/admin/inventory?low=${query?'0':'1'}&q=${query}`)).inventory);
    if(tab==='customers') return renderCustomers((await api(`/api/admin/customers?q=${query}`)).customers);
    if(tab==='payment-alerts') return renderPaymentAlerts((await api('/api/admin/payment-alerts')).alerts);
    if(tab==='system') return renderSystem((await api('/api/admin/system')).system);
    if(tab==='audit') return renderAudit((await api('/api/admin/audit')).audit);
  } catch(cause) { byId('content').innerHTML=''; error(cause.message); if(cause.message.includes('authentication')) showLogin(); }
}

function orderActions(order){
  const transitions={payment_pending:['cancelled'],payment_review_required:['placed','cancelled'],placed:['confirmed','cancelled'],confirmed:['preparing','packed','cancelled'],preparing:['out_for_delivery','cancelled'],packed:['out_for_delivery'],out_for_delivery:['delivered']};
  const actions=transitions[order.status]||[];
  if(order.status==='payment_pending'&&order.paymentStatus!=='refunded') return [];
  return order.paymentStatus==='refunded'
    ? actions.filter(status=>status==='cancelled')
    : actions;
}

function statusTone(value){return ({payment_pending:'amber',payment_review_required:'rose',placed:'sky',confirmed:'blue',preparing:'violet',packed:'indigo',out_for_delivery:'teal',delivered:'green',cancelled:'red',payment_test_completed:'slate',pending:'yellow',paid:'lime',failed:'crimson',refunded:'purple',refund_pending:'orange',partially_refunded:'fuchsia',review_required:'pink'})[String(value||'').toLowerCase()]||'slate';}
function statusBadge(value){const text=String(value||'unknown');return `<span class="status-badge tone-${statusTone(text)}">${escapeText(text.replaceAll('_',' '))}</span>`;}
function filterOptions(values,selected){return ['all',...Array.from(new Set(values.filter(Boolean))).sort()].map(value=>`<option value="${escapeText(value)}"${value===selected?' selected':''}>${value==='all'?'All':escapeText(value.replaceAll('_',' '))}</option>`).join('');}
function renderOrders(orders){currentOrders=Array.isArray(orders)?orders:[];renderOrdersView();}
function renderOrdersView(){
  const filtered=currentOrders.filter(order=>{
    const paymentTest=order.isPaymentTestOrder===true||order.fulfillmentRequired===false;
    if(orderFilters.status!=='all'&&order.status!==orderFilters.status)return false;
    if(orderFilters.payment!=='all'&&order.paymentStatus!==orderFilters.payment)return false;
    if(orderFilters.fulfillment==='required'&&paymentTest)return false;
    if(orderFilters.fulfillment==='test'&&!paymentTest)return false;
    return true;
  });
  const orderStatuses=currentOrders.map(order=>order.status);
  const paymentStatuses=currentOrders.map(order=>order.paymentStatus);
  byId('content').innerHTML=`<h2>Recent orders</h2><section class="order-filters" aria-label="Order filters"><label>Order status<select data-order-filter="status">${filterOptions(orderStatuses,orderFilters.status)}</select></label><label>Payment status<select data-order-filter="payment">${filterOptions(paymentStatuses,orderFilters.payment)}</select></label><label>Fulfillment<select data-order-filter="fulfillment"><option value="all"${orderFilters.fulfillment==='all'?' selected':''}>All</option><option value="required"${orderFilters.fulfillment==='required'?' selected':''}>Customer orders</option><option value="test"${orderFilters.fulfillment==='test'?' selected':''}>Payment tests</option></select></label><div class="order-filter-summary"><span><strong>${filtered.length}</strong> of ${currentOrders.length} orders</span><button class="secondary" data-action="clear-order-filters">Clear filters</button></div></section><div class="grid">${filtered.map(order=>{const paymentTest=order.isPaymentTestOrder===true||order.fulfillmentRequired===false;const tone=statusTone(order.status);return `<article class="card order-card order-tone-${tone}">${paymentTest?'<div class="payment-test-banner"><strong>TEST</strong><strong>NO FULFILLMENT REQUIRED</strong></div>':''}<h3>${escapeText(order.id)}</h3><div class="facts"><div class="fact"><small>Customer</small><strong>${escapeText(order.address?.name)}</strong><small>${escapeText(order.address?.phone)}</small></div><div class="fact"><small>Amount</small><strong>₹${escapeText(order.grandTotal)}</strong></div><div class="fact"><small>Payment</small>${statusBadge(order.paymentStatus)}<small>${escapeText(order.razorpayOrderId||'')} ${escapeText(order.razorpayPaymentId||order.paymentMethod)}</small></div><div class="fact"><small>Status</small>${statusBadge(order.status)}</div></div><p class="muted">${escapeText(order.address?.street)}, ${escapeText(order.address?.city)} ${escapeText(order.address?.pincode)}</p><pre>${escapeText((order.items||[]).map(item=>`${item.productName||item.name||item.productId} · ${item.size||''} ${item.colourName||item.colour||''} × ${item.quantity}`).join('\n'))}</pre>${paymentTest?'<p class="payment-test-note">Payment validation record only. Do not pack, dispatch, deliver, or adjust fashion inventory.</p>':`<div class="actions">${orderActions(order).map(status=>`<button data-action="order-status" data-id="${escapeText(order.id)}" data-value="${status}">${status.replaceAll('_',' ')}</button>`).join('')}</div>`}</article>`;}).join('')||'<p>No orders match the selected filters.</p>'}</div>`;
}
function applicationTransitions(status){return {SUBMITTED:['UNDER_REVIEW'],UNDER_REVIEW:['APPROVED','REJECTED'],APPROVED:['ACTIVE'],ACTIVE:['SUSPENDED'],SUSPENDED:['ACTIVE']}[status]||[];}
function productTransitions(status){return {SUBMITTED:['UNDER_REVIEW'],UNDER_REVIEW:['APPROVED','REJECTED'],APPROVED:['PUBLISHED'],PUBLISHED:['APPROVED']}[status]||[];}
function productRequestTransitions(status){return {SUBMITTED:['UNDER_REVIEW'],UNDER_REVIEW:['APPROVED','REJECTED']}[status]||[];}
function renderVendors(items){byId('content').innerHTML=`<h2>Shop applications</h2><div class="actions"><button class="success" data-action="create-store">Create Local Store</button></div><div class="grid">${items.map(item=>`<article class="card"><h3>${escapeText(item.shopName)}</h3><small>${escapeText(item.id)}</small><p>${escapeText(item.ownerName)} · ${escapeText(item.registeredEmail)} · ${escapeText(item.registeredMobile)}</p><p class="muted">${escapeText(item.address)}, ${escapeText(item.city)} ${escapeText(item.pincode)} — ${escapeText(item.description)}</p>${item.rejectionReason?`<p class="error">${escapeText(item.rejectionReason)}</p>`:''}<strong>${escapeText(item.status)}</strong><div class="actions">${applicationTransitions(item.status).map(status=>`<button class="${['REJECTED','SUSPENDED'].includes(status)?'danger':'success'}" data-action="vendor" data-id="${escapeText(item.id)}" data-value="${status}">${escapeText(status.replaceAll('_',' '))}</button>`).join('')}</div></article>`).join('')||'<p>No applications.</p>'}</div>`;}
function renderShopProducts(items){byId('content').innerHTML=`<h2>Shop product submissions</h2><div class="actions"><button class="success" data-action="create-shop-product">Add Product for Local Store</button></div><div class="grid">${items.map(item=>`<article class="card"><h3>${escapeText(item.name)}</h3><small>${escapeText(item.id)} · store ${escapeText(item.applicationId)}</small><p>${escapeText(item.category)} · ₹${escapeText((item.pricePaise/100).toFixed(2))} · total stock ${escapeText(item.inventory)}</p><p>${(item.variants||[]).map(variant=>`${escapeText(variant.size)}: <strong>${escapeText(variant.inventory)}</strong>`).join(' · ')}</p><p class="muted">${escapeText(item.description)}</p>${item.rejectionReason?`<p class="error">${escapeText(item.rejectionReason)}</p>`:''}<strong>${escapeText(item.status)}</strong><div class="actions"><button data-action="edit-shop-product" data-id="${escapeText(item.id)}" data-name="${escapeText(item.name)}" data-description="${escapeText(item.description)}" data-price="${escapeText((item.pricePaise/100).toFixed(2))}" data-original="${escapeText((item.originalPricePaise/100).toFixed(2))}">Edit Details</button>${productTransitions(item.status).map(status=>`<button class="${status==='REJECTED'?'danger':'success'}" data-action="shop-product" data-id="${escapeText(item.id)}" data-value="${status}">${escapeText(status==='APPROVED'&&item.status==='PUBLISHED'?'UNPUBLISH':status.replaceAll('_',' '))}</button>`).join('')}</div></article>`).join('')||'<p>No shop product submissions.</p>'}</div>`;}
function renderShopProductRequests(items){byId('content').innerHTML=`<h2>Product change requests</h2><div class="grid">${items.map(item=>{const proposed=item.proposedProduct?JSON.stringify(item.proposedProduct,null,2):'';return `<article class="card"><h3>${escapeText(item.productName||item.productId)}</h3><p>${escapeText(item.shopName||item.applicationId)} / ${escapeText(item.action)}</p>${proposed?`<pre>${escapeText(proposed)}</pre>`:'<p class="muted">Seller requested this product be unpublished.</p>'}${item.rejectionReason?`<p class="error">${escapeText(item.rejectionReason)}</p>`:''}<strong>${escapeText(item.status)}</strong><div class="actions">${productRequestTransitions(item.status).map(status=>`<button class="${status==='REJECTED'?'danger':'success'}" data-action="shop-product-request" data-id="${escapeText(item.id)}" data-value="${status}">${escapeText(status.replaceAll('_',' '))}</button>`).join('')}</div></article>`;}).join('')||'<p>No product change requests.</p>'}</div>`;}
function renderInventory(items){byId('content').innerHTML=`<h2>Low stock inventory</h2><p class="muted">Showing variants with 5 or fewer units.</p><table><thead><tr><th>Product</th><th>Variant</th><th>Stock</th><th>Action</th></tr></thead><tbody>${items.map(item=>`<tr><td>${escapeText(item.productName)}</td><td>${escapeText(item.size)} / ${escapeText(item.colour)}<br><small>${escapeText(item.variantId)}</small></td><td><strong>${escapeText(item.stock)}</strong></td><td><button data-action="inventory" data-id="${escapeText(item.variantId)}">Adjust</button></td></tr>`).join('')}</tbody></table>`;}
function renderCustomers(items){byId('content').innerHTML=`<h2>Customers</h2><div class="actions"><button class="success" data-action="create-owner">Create Store Owner Account</button></div><table><thead><tr><th>Customer</th><th>Contact</th><th>Status</th><th>Action</th></tr></thead><tbody>${items.map(item=>`<tr><td>${escapeText(item.name)}<br><small>${escapeText(item.id)}</small></td><td>${escapeText(item.email)}<br>${escapeText(item.phone)}</td><td>${item.is_active?'Active':'Disabled'}</td><td><div class="actions"><button data-action="reset-customer-password" data-id="${escapeText(item.id)}">Reset Password</button><button class="${item.is_active?'danger':'success'}" data-action="customer" data-id="${escapeText(item.id)}" data-value="${item.is_active?'false':'true'}">${item.is_active?'Disable':'Enable'}</button></div></td></tr>`).join('')}</tbody></table>`;}
function renderPaymentAlerts(items){byId('content').innerHTML=`<h2>Payment alerts requiring attention</h2><table><thead><tr><th>Time</th><th>Event</th><th>Vibe4You order</th><th>Payment reference</th><th>Status</th></tr></thead><tbody>${items.map(item=>`<tr><td>${escapeText(item.recordedAt)}</td><td><strong>${escapeText(item.type)}</strong><br><small>${escapeText(item.entityId)}</small></td><td>${escapeText(item.styleDashOrderId||'Unmatched')}</td><td>${escapeText(item.razorpayPaymentId)}</td><td>${escapeText(item.status)}</td></tr>`).join('')}</tbody></table>${items.length?'':'<p>No payment alerts.</p>'}`;}
function renderSystem(system){byId('content').innerHTML=`<h2>System</h2><div class="facts"><div class="fact"><small>Admin service</small><strong>${escapeText(system.adminService)}</strong></div><div class="fact"><small>Database</small><strong>${escapeText(system.database.database)}</strong><small>Migration ${escapeText(system.database.migrationVersion)}</small></div><div class="fact"><small>Public service</small><strong>${escapeText(system.publicService.status)}</strong></div><div class="fact"><small>Payment mode</small><strong>${escapeText(system.paymentMode)}</strong></div><div class="fact"><small>Latest backup</small><strong>${escapeText(system.latestBackup||'None')}</strong></div></div>`;}
function renderAudit(items){byId('content').innerHTML=`<h2>Administrator audit</h2><table><thead><tr><th>Time</th><th>Action</th><th>Target</th><th>Result</th></tr></thead><tbody>${items.map(item=>`<tr><td>${escapeText(item.created_at)}</td><td>${escapeText(item.action)}</td><td>${escapeText(item.target_type)} ${escapeText(item.target_id)}</td><td>${escapeText(item.result)}</td></tr>`).join('')}</tbody></table>`;}

api('/api/admin/me').then(result=>{csrfToken=result.csrfToken;showApp(result.admin);}).catch(showLogin);
