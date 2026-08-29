let csrfToken = '';
let activeTab = 'orders';

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

function ask(label, fallback='') {
  const value=prompt(label,fallback);
  if(value===null)return null;
  return value.trim();
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
  const name=ask('Store owner full name:'); if(!name)return;
  const email=ask('Store owner email (used for login):'); if(!email)return;
  const phone=ask('Mobile number (optional):')||'';
  const password=ask('Temporary password (8+ characters):'); if(!password)return;
  await api('/api/admin/customers',{method:'POST',body:JSON.stringify({name,email,phone:phone||undefined,password})});
  alert(`Owner account created for ${email}. Share the temporary password securely.`);
}
async function resetCustomerPassword(userId){
  const password=ask('New temporary password (8+ characters):'); if(!password)return;
  await api(`/api/admin/customers/${encodeURIComponent(userId)}/password`,{method:'PATCH',body:JSON.stringify({password})});
  alert('Temporary password updated. Existing sessions were signed out.');
}
async function createLocalStore(){
  const ownerUserId=ask('Owner customer ID (copy from Customers tab):'); if(!ownerUserId)return;
  const shopName=ask('Store name:'); if(!shopName)return;
  const ownerName=ask('Owner name:'); if(!ownerName)return;
  const category=ask('Category:','Clothing & Fashion'); if(!category)return;
  const description=ask('Store description:'); if(!description)return;
  const address=ask('Store address:'); if(!address)return;
  const city=ask('City:','Neemuch')||'Neemuch';
  const state=ask('State:','Madhya Pradesh')||'Madhya Pradesh';
  const pincode=ask('Pincode:','458441')||'458441';
  const businessInformation=ask('Business information (optional):')||'';
  await api('/api/admin/vendors',{method:'POST',body:JSON.stringify({ownerUserId,shopName,ownerName,category,description,address,city,state,pincode,businessInformation})});
  alert(`${shopName} created and activated.`);
}
async function createStoreProduct(){
  const applicationId=ask('Store application ID (copy from Shop Applications):'); if(!applicationId)return;
  const name=ask('Product name:'); if(!name)return;
  const description=ask('Product description:'); if(!description)return;
  const brand=ask('Brand (optional):')||'';
  const department=ask('Department: men, women, kids, unisex, footwear, accessories','unisex')||'unisex';
  const category=ask('Category:','Clothing & Fashion')||'Clothing & Fashion';
  const price=Number(ask('Selling price in rupees:')); if(!Number.isFinite(price)||price<1)throw new Error('Enter a valid selling price.');
  const originalRaw=ask('Original/MRP price in rupees:',String(price)); const originalPrice=Number(originalRaw||price);
  const variants=parseVariants(ask('Sizes and stock, e.g. S:5, M:8, L:3:'));
  const colourName=ask('Colour name:','Multi')||'Multi';
  const colourHex=ask('Colour hex (optional, e.g. #000000):')||'';
  const images=ask('HTTPS image URLs separated by commas:'); if(!images)return;
  const imageUrls=images.split(',').map(value=>value.trim()).filter(Boolean);
  const payload={applicationId,name,description,brand:brand||undefined,department,category,pricePaise:Math.round(price*100),originalPricePaise:Math.round(originalPrice*100),variants,colourName,colourHex:colourHex||undefined,imageUrls,attributes:{}};
  await api('/api/admin/shop-products',{method:'POST',body:JSON.stringify(payload)});
  alert(`${name} published for the selected local store.`);
}
async function editStoreProduct(button){
  const name=ask('Product name:',button.dataset.name||''); if(name===null)return;
  const description=ask('Description:',button.dataset.description||''); if(description===null)return;
  const price=ask('Selling price in rupees:',button.dataset.price||''); if(price===null)return;
  const original=ask('Original/MRP price in rupees:',button.dataset.original||price); if(original===null)return;
  const payload={name,description,pricePaise:Math.round(Number(price)*100),originalPricePaise:Math.round(Number(original)*100)};
  await api(`/api/admin/shop-products/${encodeURIComponent(button.dataset.id)}/details`,{method:'PATCH',body:JSON.stringify(payload)});
}
byId('content').addEventListener('click', async event => {
  const button=event.target.closest('[data-action]'); if(!button)return;
  button.disabled=true; error('');
  try {
    const action=button.dataset.action;
    if(action==='create-owner') await createOwnerAccount();
    if(action==='reset-customer-password') await resetCustomerPassword(button.dataset.id);
    if(action==='create-store') await createLocalStore();
    if(action==='create-shop-product') await createStoreProduct();
    if(action==='edit-shop-product') await editStoreProduct(button);
    if(action==='order-status') await api(`/api/admin/orders/${encodeURIComponent(button.dataset.id)}/status`,{method:'PATCH',body:JSON.stringify({status:button.dataset.value})});
    if(action==='vendor') { const status=button.dataset.value; const reason=['REJECTED','SUSPENDED'].includes(status)?prompt(`Enter the ${status.toLowerCase()} reason:`):null; if(['REJECTED','SUSPENDED'].includes(status)&&!reason)return; await api(`/api/admin/vendors/${encodeURIComponent(button.dataset.id)}`,{method:'PATCH',body:JSON.stringify({status,reason})}); }
    if(action==='shop-product') { const status=button.dataset.value; const reason=status==='REJECTED'?prompt('Enter the rejection reason:'):null; if(status==='REJECTED'&&!reason)return; await api(`/api/admin/shop-products/${encodeURIComponent(button.dataset.id)}`,{method:'PATCH',body:JSON.stringify({status,reason})}); }
    if(action==='shop-product-request') { const status=button.dataset.value; const reason=status==='REJECTED'?prompt('Enter the rejection reason:'):null; if(status==='REJECTED'&&!reason)return; await api(`/api/admin/shop-product-requests/${encodeURIComponent(button.dataset.id)}`,{method:'PATCH',body:JSON.stringify({status,reason})}); }
    if(action==='inventory') { const raw=prompt('Enter stock adjustment, for example 5 or -2:'); if(raw===null)return; await api(`/api/admin/inventory/${encodeURIComponent(button.dataset.id)}`,{method:'PATCH',body:JSON.stringify({delta:Number(raw)})}); }
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

function renderOrders(orders){byId('content').innerHTML=`<h2>Recent orders</h2><div class="grid">${orders.map(order=>{const paymentTest=order.isPaymentTestOrder===true||order.fulfillmentRequired===false;return `<article class="card">${paymentTest?'<div class="payment-test-banner"><strong>TEST</strong><strong>NO FULFILLMENT REQUIRED</strong></div>':''}<h3>${escapeText(order.id)}</h3><div class="facts"><div class="fact"><small>Customer</small><strong>${escapeText(order.address?.name)}</strong><small>${escapeText(order.address?.phone)}</small></div><div class="fact"><small>Amount</small><strong>₹${escapeText(order.grandTotal)}</strong></div><div class="fact"><small>Payment</small><strong>${escapeText(order.paymentStatus)}</strong><small>${escapeText(order.razorpayOrderId||'')} ${escapeText(order.razorpayPaymentId||order.paymentMethod)}</small></div><div class="fact"><small>Status</small><strong>${escapeText(order.status)}</strong></div></div><p class="muted">${escapeText(order.address?.street)}, ${escapeText(order.address?.city)} ${escapeText(order.address?.pincode)}</p><pre>${escapeText((order.items||[]).map(item=>`${item.productName||item.name||item.productId} · ${item.size||''} ${item.colourName||item.colour||''} × ${item.quantity}`).join('\n'))}</pre>${paymentTest?'<p class="payment-test-note">Payment validation record only. Do not pack, dispatch, deliver, or adjust fashion inventory.</p>':`<div class="actions">${orderActions(order).map(status=>`<button data-action="order-status" data-id="${escapeText(order.id)}" data-value="${status}">${status.replaceAll('_',' ')}</button>`).join('')}</div>`}</article>`;}).join('')||'<p>No orders found.</p>'}</div>`;}
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
