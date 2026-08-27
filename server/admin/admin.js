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
byId('content').addEventListener('click', async event => {
  const button=event.target.closest('[data-action]'); if(!button)return;
  button.disabled=true; error('');
  try {
    const action=button.dataset.action;
    if(action==='order-status') await api(`/api/admin/orders/${encodeURIComponent(button.dataset.id)}/status`,{method:'PATCH',body:JSON.stringify({status:button.dataset.value})});
    if(action==='fulfillment-override') {
      const allowed=['NEW','PROCESSING','READY','SHIPPED','DELIVERED'];
      const rawStatus=prompt('Set shop fulfillment status (NEW, PROCESSING, READY, SHIPPED, DELIVERED):',button.dataset.status||'NEW');
      if(rawStatus===null)return;
      const status=rawStatus.trim().toUpperCase();
      if(!allowed.includes(status))throw new Error('Enter a valid shop fulfillment status.');
      const reason=prompt('Reason for this administrator override (required):');
      if(reason===null||reason.trim().length<5)return;
      const payload={status,reason:reason.trim()};
      if(status==='SHIPPED'){
        const carrier=prompt('Carrier (optional):',button.dataset.carrier||''); if(carrier===null)return;
        const tracking=prompt('Tracking number (optional):',button.dataset.tracking||''); if(tracking===null)return;
        if(Boolean(carrier.trim())!==Boolean(tracking.trim()))throw new Error('Enter both carrier and tracking number, or leave both blank.');
        if(carrier.trim()){payload.carrier=carrier.trim();payload.trackingNumber=tracking.trim();}
      }
      await api(`/api/admin/orders/${encodeURIComponent(button.dataset.order)}/fulfillment/${encodeURIComponent(button.dataset.application)}`,{method:'PATCH',body:JSON.stringify(payload)});
    }
    if(action==='return-item') {
      const status=button.dataset.value;
      const note=status==='REJECTED'?prompt('Reason for rejecting this return/exchange request (required):'):null;
      if(status==='REJECTED'&&(!note||note.trim().length<2))return;
      let resolutionReference=null;
      if(['EXCHANGED','REFUND_PENDING'].includes(status)) resolutionReference=prompt('Resolution/reference note (optional):')||null;
      await api(`/api/admin/returns/items/${encodeURIComponent(button.dataset.id)}`,{method:'PATCH',body:JSON.stringify({status,note:note?.trim()||null,resolutionReference:resolutionReference?.trim()||null})});
    }
    if(action==='return-cancellation') {
      const status=button.dataset.value;
      const note=status==='REJECTED'?prompt('Reason for rejecting this cancellation request (required):'):null;
      if(status==='REJECTED'&&(!note||note.trim().length<2))return;
      await api(`/api/admin/returns/cancellations/${encodeURIComponent(button.dataset.order)}`,{method:'PATCH',body:JSON.stringify({status,note:note?.trim()||null})});
    }
    if(action==='vendor') { const status=button.dataset.value; const reason=['REJECTED','SUSPENDED'].includes(status)?prompt(`Enter the ${status.toLowerCase()} reason:`):null; if(['REJECTED','SUSPENDED'].includes(status)&&!reason)return; await api(`/api/admin/vendors/${encodeURIComponent(button.dataset.id)}`,{method:'PATCH',body:JSON.stringify({status,reason})}); }
    if(action==='shop-product') { const status=button.dataset.value; const reason=status==='REJECTED'?prompt('Enter the rejection reason:'):null; if(status==='REJECTED'&&!reason)return; await api(`/api/admin/shop-products/${encodeURIComponent(button.dataset.id)}`,{method:'PATCH',body:JSON.stringify({status,reason})}); }
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
    if(tab==='returns') return renderReturns(await api('/api/admin/returns'));
    if(tab==='vendors') return renderVendors((await api('/api/admin/vendors')).applications);
    if(tab==='shop-products') return renderShopProducts((await api('/api/admin/shop-products')).products);
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

function renderShopFulfillments(order){
  const segments=order.shopFulfillments||[];
  if(!segments.length)return '<p class="muted">No seller shop segments are linked to this order.</p>';
  return `<div class="facts">${segments.map(item=>`<div class="fact"><small>Shop fulfillment</small><strong>${escapeText(item.shopName)} · ${escapeText(item.status)}</strong>${item.shipping?`<small>${escapeText(item.shipping.carrier)} · ${escapeText(item.shipping.trackingNumber)}</small>`:'<small>No tracking attached</small>'}<button data-action="fulfillment-override" data-order="${escapeText(order.id)}" data-application="${escapeText(item.applicationId)}" data-status="${escapeText(item.status)}" data-carrier="${escapeText(item.shipping?.carrier||'')}" data-tracking="${escapeText(item.shipping?.trackingNumber||'')}">Override shop fulfillment</button></div>`).join('')}</div>`;
}

function renderOrders(orders){byId('content').innerHTML=`<h2>Recent orders</h2><div class="grid">${orders.map(order=>{const paymentTest=order.isPaymentTestOrder===true||order.fulfillmentRequired===false;return `<article class="card">${paymentTest?'<div class="payment-test-banner"><strong>TEST</strong><strong>NO FULFILLMENT REQUIRED</strong></div>':''}<h3>${escapeText(order.id)}</h3><div class="facts"><div class="fact"><small>Customer</small><strong>${escapeText(order.address?.name)}</strong><small>${escapeText(order.address?.phone)}</small></div><div class="fact"><small>Amount</small><strong>₹${escapeText(order.grandTotal)}</strong></div><div class="fact"><small>Payment</small><strong>${escapeText(order.paymentStatus)}</strong><small>${escapeText(order.razorpayOrderId||'')} ${escapeText(order.razorpayPaymentId||order.paymentMethod)}</small></div><div class="fact"><small>Status</small><strong>${escapeText(order.status)}</strong></div></div><p class="muted">${escapeText(order.address?.street)}, ${escapeText(order.address?.city)} ${escapeText(order.address?.pincode)}</p><pre>${escapeText((order.items||[]).map(item=>`${item.productName||item.name||item.productId} · ${item.size||''} ${item.colourName||item.colour||''} × ${item.quantity}`).join('\n'))}</pre>${paymentTest?'':renderShopFulfillments(order)}${paymentTest?'<p class="payment-test-note">Payment validation record only. Do not pack, dispatch, deliver, or adjust fashion inventory.</p>':`<div class="actions">${orderActions(order).map(status=>`<button data-action="order-status" data-id="${escapeText(order.id)}" data-value="${status}">${status.replaceAll('_',' ')}</button>`).join('')}</div>`}</article>`;}).join('')||'<p>No orders found.</p>'}</div>`;}
function returnTransitions(item){
  if(item.status==='REQUESTED')return ['UNDER_REVIEW','REJECTED'];
  if(item.status==='UNDER_REVIEW')return ['APPROVED','REJECTED'];
  if(item.requestType==='SIZE_EXCHANGE')return {APPROVED:['PICKUP_PENDING'],PICKUP_PENDING:['RECEIVED'],RECEIVED:['EXCHANGED']}[item.status]||[];
  if(item.requestType==='ISSUE_RETURN')return {APPROVED:['PICKUP_PENDING'],PICKUP_PENDING:['RECEIVED'],RECEIVED:['REFUND_PENDING']}[item.status]||[];
  return [];
}
function cancellationTransitions(item){return {REQUESTED:['UNDER_REVIEW','REJECTED'],UNDER_REVIEW:['APPROVED','REJECTED']}[item.status]||[];}
function renderReturns(result){
  const items=result.items||[]; const cancellations=result.cancellations||[];
  const itemCards=items.map(item=>`<article class="card"><h3>${escapeText(item.requestType.replaceAll('_',' '))}</h3><p><strong>${escapeText(item.productName)}</strong> · ${escapeText(item.shopName)} · Order ${escapeText(item.orderId)}</p><p class="muted">Reason: ${escapeText(item.reason.replaceAll('_',' '))}${item.details?` · ${escapeText(item.details)}`:''}</p><div class="facts"><div class="fact"><small>Status</small><strong>${escapeText(item.status)}</strong></div><div class="fact"><small>Quantity</small><strong>${escapeText(item.quantity)}</strong></div><div class="fact"><small>Item subtotal snapshot</small><strong>₹${escapeText(item.itemSubtotal)}</strong></div></div>${item.sellerNote?`<p class="muted">Seller note: ${escapeText(item.sellerNote)}</p>`:''}${item.adminNote?`<p class="muted">Admin note: ${escapeText(item.adminNote)}</p>`:''}<div class="actions">${returnTransitions(item).map(status=>`<button class="${status==='REJECTED'?'danger':'success'}" data-action="return-item" data-id="${escapeText(item.id)}" data-value="${status}">${escapeText(status.replaceAll('_',' '))}</button>`).join('')}</div></article>`).join('');
  const cancellationCards=cancellations.map(item=>`<article class="card"><h3>Order cancellation · ${escapeText(item.orderId)}</h3><p>${escapeText(item.customerName||'Customer')} · order ${escapeText(item.orderStatus)} · payment ${escapeText(item.paymentStatus)}</p><p class="muted">Reason: ${escapeText(String(item.reason||'').replaceAll('_',' '))}${item.details?` · ${escapeText(item.details)}`:''}</p><strong>${escapeText(item.status)}</strong>${item.status==='APPROVED'?'<p class="muted"><strong>Approved request only.</strong> This does not cancel or refund the order. Complete the protected order/refund action separately.</p>':''}<div class="actions">${cancellationTransitions(item).map(status=>`<button class="${status==='REJECTED'?'danger':'success'}" data-action="return-cancellation" data-order="${escapeText(item.orderId)}" data-value="${status}">${escapeText(status==='APPROVED'?'APPROVE REQUEST':status.replaceAll('_',' '))}</button>`).join('')}</div></article>`).join('');
  byId('content').innerHTML=`<h2>Returns, exchanges & cancellations</h2><p class="muted">Approving a request never performs a Razorpay refund or global order cancellation automatically.</p><h3>Item requests</h3><div class="grid">${itemCards||'<p>No item return or exchange requests.</p>'}</div><h3>Cancellation requests</h3><div class="grid">${cancellationCards||'<p>No cancellation requests.</p>'}</div>`;
}
function applicationTransitions(status){return {SUBMITTED:['UNDER_REVIEW'],UNDER_REVIEW:['APPROVED','REJECTED'],APPROVED:['ACTIVE'],ACTIVE:['SUSPENDED'],SUSPENDED:['ACTIVE']}[status]||[];}
function productTransitions(status){return {SUBMITTED:['UNDER_REVIEW'],UNDER_REVIEW:['APPROVED','REJECTED'],APPROVED:['PUBLISHED'],PUBLISHED:['APPROVED']}[status]||[];}
function renderVendors(items){byId('content').innerHTML=`<h2>Shop applications</h2><div class="grid">${items.map(item=>`<article class="card"><h3>${escapeText(item.shopName)}</h3><p>${escapeText(item.ownerName)} · ${escapeText(item.registeredEmail)} · ${escapeText(item.registeredMobile)}</p><p class="muted">${escapeText(item.address)}, ${escapeText(item.city)} ${escapeText(item.pincode)} — ${escapeText(item.description)}</p>${item.rejectionReason?`<p class="error">${escapeText(item.rejectionReason)}</p>`:''}<strong>${escapeText(item.status)}</strong><div class="actions">${applicationTransitions(item.status).map(status=>`<button class="${['REJECTED','SUSPENDED'].includes(status)?'danger':'success'}" data-action="vendor" data-id="${escapeText(item.id)}" data-value="${status}">${escapeText(status.replaceAll('_',' '))}</button>`).join('')}</div></article>`).join('')||'<p>No applications.</p>'}</div>`;}
function renderShopProducts(items){byId('content').innerHTML=`<h2>Shop product submissions</h2><div class="grid">${items.map(item=>`<article class="card"><h3>${escapeText(item.name)}</h3><p>${escapeText(item.category)} · ₹${escapeText((item.pricePaise/100).toFixed(2))} · stock ${escapeText(item.inventory)}</p><p class="muted">${escapeText(item.description)}</p>${item.rejectionReason?`<p class="error">${escapeText(item.rejectionReason)}</p>`:''}<strong>${escapeText(item.status)}</strong><div class="actions">${productTransitions(item.status).map(status=>`<button class="${status==='REJECTED'?'danger':'success'}" data-action="shop-product" data-id="${escapeText(item.id)}" data-value="${status}">${escapeText(status==='APPROVED'&&item.status==='PUBLISHED'?'UNPUBLISH':status.replaceAll('_',' '))}</button>`).join('')}</div></article>`).join('')||'<p>No shop product submissions.</p>'}</div>`;}
function renderInventory(items){byId('content').innerHTML=`<h2>Low stock inventory</h2><p class="muted">Showing variants with 5 or fewer units.</p><table><thead><tr><th>Product</th><th>Variant</th><th>Stock</th><th>Action</th></tr></thead><tbody>${items.map(item=>`<tr><td>${escapeText(item.productName)}</td><td>${escapeText(item.size)} / ${escapeText(item.colour)}<br><small>${escapeText(item.variantId)}</small></td><td><strong>${escapeText(item.stock)}</strong></td><td><button data-action="inventory" data-id="${escapeText(item.variantId)}">Adjust</button></td></tr>`).join('')}</tbody></table>`;}
function renderCustomers(items){byId('content').innerHTML=`<h2>Customers</h2><table><thead><tr><th>Customer</th><th>Contact</th><th>Status</th><th>Action</th></tr></thead><tbody>${items.map(item=>`<tr><td>${escapeText(item.name)}<br><small>${escapeText(item.id)}</small></td><td>${escapeText(item.email)}<br>${escapeText(item.phone)}</td><td>${item.is_active?'Active':'Disabled'}</td><td><button class="${item.is_active?'danger':'success'}" data-action="customer" data-id="${escapeText(item.id)}" data-value="${item.is_active?'false':'true'}">${item.is_active?'Disable':'Enable'}</button></td></tr>`).join('')}</tbody></table>`;}
function renderPaymentAlerts(items){byId('content').innerHTML=`<h2>Payment alerts requiring attention</h2><table><thead><tr><th>Time</th><th>Event</th><th>StyleDash order</th><th>Payment reference</th><th>Status</th></tr></thead><tbody>${items.map(item=>`<tr><td>${escapeText(item.recordedAt)}</td><td><strong>${escapeText(item.type)}</strong><br><small>${escapeText(item.entityId)}</small></td><td>${escapeText(item.styleDashOrderId||'Unmatched')}</td><td>${escapeText(item.razorpayPaymentId)}</td><td>${escapeText(item.status)}</td></tr>`).join('')}</tbody></table>${items.length?'':'<p>No payment alerts.</p>'}`;}
function renderSystem(system){byId('content').innerHTML=`<h2>System</h2><div class="facts"><div class="fact"><small>Admin service</small><strong>${escapeText(system.adminService)}</strong></div><div class="fact"><small>Database</small><strong>${escapeText(system.database.database)}</strong><small>Migration ${escapeText(system.database.migrationVersion)}</small></div><div class="fact"><small>Public service</small><strong>${escapeText(system.publicService.status)}</strong></div><div class="fact"><small>Payment mode</small><strong>${escapeText(system.paymentMode)}</strong></div><div class="fact"><small>Latest backup</small><strong>${escapeText(system.latestBackup||'None')}</strong></div></div>`;}
function renderAudit(items){byId('content').innerHTML=`<h2>Administrator audit</h2><table><thead><tr><th>Time</th><th>Action</th><th>Target</th><th>Result</th></tr></thead><tbody>${items.map(item=>`<tr><td>${escapeText(item.created_at)}</td><td>${escapeText(item.action)}</td><td>${escapeText(item.target_type)} ${escapeText(item.target_id)}</td><td>${escapeText(item.result)}</td></tr>`).join('')}</tbody></table>`;}

api('/api/admin/me').then(result=>{csrfToken=result.csrfToken;showApp(result.admin);}).catch(showLogin);
