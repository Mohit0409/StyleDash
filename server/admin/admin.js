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
    if(action==='vendor') await api(`/api/admin/vendors/${encodeURIComponent(button.dataset.id)}`,{method:'PATCH',body:JSON.stringify({status:button.dataset.value})});
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
    if(tab==='inventory') return renderInventory((await api(`/api/admin/inventory?low=${query?'0':'1'}&q=${query}`)).inventory);
    if(tab==='customers') return renderCustomers((await api(`/api/admin/customers?q=${query}`)).customers);
    if(tab==='system') return renderSystem((await api('/api/admin/system')).system);
    if(tab==='audit') return renderAudit((await api('/api/admin/audit')).audit);
  } catch(cause) { byId('content').innerHTML=''; error(cause.message); if(cause.message.includes('authentication')) showLogin(); }
}

function renderOrders(orders){byId('content').innerHTML=`<h2>Recent orders</h2><div class="grid">${orders.map(order=>`<article class="card"><h3>${escapeText(order.id)}</h3><div class="facts"><div class="fact"><small>Customer</small><strong>${escapeText(order.address?.name)}</strong><small>${escapeText(order.address?.phone)}</small></div><div class="fact"><small>Amount</small><strong>₹${escapeText(order.grandTotal)}</strong></div><div class="fact"><small>Payment</small><strong>${escapeText(order.paymentStatus)}</strong><small>${escapeText(order.razorpayOrderId||'')} ${escapeText(order.razorpayPaymentId||order.paymentMethod)}</small></div><div class="fact"><small>Status</small><strong>${escapeText(order.status)}</strong></div></div><p class="muted">${escapeText(order.address?.street)}, ${escapeText(order.address?.city)} ${escapeText(order.address?.pincode)}</p><pre>${escapeText((order.items||[]).map(item=>`${item.name||item.productId} · ${item.size||''} ${item.colour||''} × ${item.quantity}`).join('\n'))}</pre><div class="actions">${['confirmed','preparing','packed','out_for_delivery','delivered','cancelled'].map(status=>`<button data-action="order-status" data-id="${escapeText(order.id)}" data-value="${status}">${status.replaceAll('_',' ')}</button>`).join('')}</div></article>`).join('')||'<p>No orders found.</p>'}</div>`;}
function renderVendors(items){byId('content').innerHTML=`<h2>Vendor applications</h2><div class="grid">${items.map(item=>`<article class="card"><h3>${escapeText(item.shop_name)}</h3><p>${escapeText(item.owner_name)} · ${escapeText(item.email)} · ${escapeText(item.phone)}</p><p class="muted">${escapeText(item.address)} ${escapeText(item.pincode)} — ${escapeText(item.description)}</p><strong>${escapeText(item.status)}</strong>${item.status==='pending'?`<div class="actions"><button class="success" data-action="vendor" data-id="${escapeText(item.id)}" data-value="approved">Approve</button><button class="danger" data-action="vendor" data-id="${escapeText(item.id)}" data-value="rejected">Reject</button></div>`:''}</article>`).join('')||'<p>No applications.</p>'}</div>`;}
function renderInventory(items){byId('content').innerHTML=`<h2>Low stock inventory</h2><p class="muted">Showing variants with 5 or fewer units.</p><table><thead><tr><th>Product</th><th>Variant</th><th>Stock</th><th>Action</th></tr></thead><tbody>${items.map(item=>`<tr><td>${escapeText(item.productName)}</td><td>${escapeText(item.size)} / ${escapeText(item.colour)}<br><small>${escapeText(item.variantId)}</small></td><td><strong>${escapeText(item.stock)}</strong></td><td><button data-action="inventory" data-id="${escapeText(item.variantId)}">Adjust</button></td></tr>`).join('')}</tbody></table>`;}
function renderCustomers(items){byId('content').innerHTML=`<h2>Customers</h2><table><thead><tr><th>Customer</th><th>Contact</th><th>Status</th><th>Action</th></tr></thead><tbody>${items.map(item=>`<tr><td>${escapeText(item.name)}<br><small>${escapeText(item.id)}</small></td><td>${escapeText(item.email)}<br>${escapeText(item.phone)}</td><td>${item.is_active?'Active':'Disabled'}</td><td><button class="${item.is_active?'danger':'success'}" data-action="customer" data-id="${escapeText(item.id)}" data-value="${item.is_active?'false':'true'}">${item.is_active?'Disable':'Enable'}</button></td></tr>`).join('')}</tbody></table>`;}
function renderSystem(system){byId('content').innerHTML=`<h2>System</h2><div class="facts"><div class="fact"><small>Admin service</small><strong>${escapeText(system.adminService)}</strong></div><div class="fact"><small>Database</small><strong>${escapeText(system.database.database)}</strong><small>Migration ${escapeText(system.database.migrationVersion)}</small></div><div class="fact"><small>Public service</small><strong>${escapeText(system.publicService.status)}</strong></div><div class="fact"><small>Payment mode</small><strong>${escapeText(system.paymentMode)}</strong></div><div class="fact"><small>Latest backup</small><strong>${escapeText(system.latestBackup||'None')}</strong></div></div>`;}
function renderAudit(items){byId('content').innerHTML=`<h2>Administrator audit</h2><table><thead><tr><th>Time</th><th>Action</th><th>Target</th><th>Result</th></tr></thead><tbody>${items.map(item=>`<tr><td>${escapeText(item.created_at)}</td><td>${escapeText(item.action)}</td><td>${escapeText(item.target_type)} ${escapeText(item.target_id)}</td><td>${escapeText(item.result)}</td></tr>`).join('')}</tbody></table>`;}

api('/api/admin/me').then(result=>{csrfToken=result.csrfToken;showApp(result.admin);}).catch(showLogin);
