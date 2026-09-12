let csrfToken = '';
let activeTab = 'orders';
let currentOrders = [];
let orderFilters = {status:'all', payment:'all', fulfillment:'all'};
let currentShopProducts = [];
let shopProductStores = [];
let shopProductFilter = 'all';
let currentVendors = [];
let adminFilters = {
  vendors:{status:'all',category:'all'},
  'shop-products':{status:'all',category:'all'},
  'shop-product-requests':{status:'all',action:'all'},
  inventory:{stock:'low'},
  customers:{status:'all'},
  'payment-alerts':{status:'all',type:'all'},
  audit:{result:'all',target:'all',action:'all'},
};

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
byId('content').addEventListener('change', event => {
  const orderControl=event.target.closest('[data-order-filter]');
  if(orderControl){orderFilters[orderControl.dataset.orderFilter]=orderControl.value;renderOrdersView();return;}
  const shopControl=event.target.closest('[data-shop-product-filter]');
  if(shopControl){shopProductFilter=shopControl.value;loadTab(activeTab);return;}
  const adminControl=event.target.closest('[data-admin-filter]');
  if(adminControl){adminFilters[activeTab][adminControl.dataset.adminFilter]=adminControl.value;loadTab(activeTab);}
});

function status(message) { byId('app-status').textContent = message || ''; }
function newColourCard(source={}) {
  const key=typeof crypto?.randomUUID==='function'?crypto.randomUUID():`colour-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return {cardKey:key,colourName:source.colourName||'',colourHex:source.colourHex||'',imageUrls:Array.isArray(source.imageUrls)?source.imageUrls.filter(value=>typeof value==='string'):[],pendingFiles:[],httpsDraft:'',sizes:Array.isArray(source.sizes)&&source.sizes.length?source.sizes.map(size=>({id:typeof size.id==='string'?size.id:undefined,size:size.size||'',inventory:Number.isInteger(size.inventory)?size.inventory:0})):[{size:'',inventory:0}]};
}
function filePreview(file){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onerror=()=>reject(new Error('The selected image could not be read.'));reader.onload=()=>resolve(String(reader.result||''));reader.readAsDataURL(file);});}
async function queueColourFiles(colour,files){
  const selected=Array.from(files||[]); if(!selected.length)return;
  if(colour.imageUrls.length+colour.pendingFiles.length+selected.length>8)throw new Error('Each colour can have at most 8 images.');
  for(const file of selected){validateAdminImageFile(file);colour.pendingFiles.push({file,preview:await filePreview(file)});}
}
async function uploadColourVariantImages(colours){
  for(const colour of colours){const httpsUrls=String(colour.httpsDraft||'').split(/\r?\n/).map(value=>value.trim()).filter(Boolean);const count=colour.imageUrls.length+httpsUrls.length+colour.pendingFiles.length;if(count<1||count>8)throw new Error('Each colour needs between 1 and 8 images.');}
  const total=colours.reduce((sum,colour)=>sum+colour.pendingFiles.length,0); let offset=0;
  const result=[];
  for(const colour of colours){const files=colour.pendingFiles.map(entry=>entry.file);const uploaded=files.length?await uploadAdminProductImages(files,offset,total):[];offset+=files.length;const httpsUrls=String(colour.httpsDraft||'').split(/\r?\n/).map(value=>value.trim()).filter(Boolean);result.push({colourName:colour.colourName,colourHex:colour.colourHex||undefined,imageUrls:[...colour.imageUrls,...httpsUrls,...uploaded],sizes:colour.sizes.map(size=>({...size,inventory:Number(size.inventory)}))});}
  return result;
}
function formDialog(title, fields, submitLabel='Continue') {
  return new Promise(resolve => {
    const dialog=byId('admin-dialog');
    const form=byId('admin-dialog-form');
    const fieldsRoot=byId('admin-dialog-fields');
    byId('admin-dialog-title').textContent=title;
    byId('admin-dialog-submit').textContent=submitLabel;
    byId('admin-dialog-error').textContent='';
    fieldsRoot.replaceChildren();
    let colourVariantsGetter=null;
    for(const field of fields){
      if(field.type==='colourVariants'){
        const section=document.createElement('section');section.className='variant-editor';
        const heading=document.createElement('h3');heading.textContent=field.label;section.appendChild(heading);
        const hint=document.createElement('p');hint.className='muted';hint.textContent='Each colour has its own images, sizes and stock. Local files upload only when you save.';section.appendChild(hint);
        const cards=document.createElement('div');cards.className='variant-cards';section.appendChild(cards);
        const addColour=document.createElement('button');addColour.type='button';addColour.className='secondary';addColour.textContent='+ Add another colour';section.appendChild(addColour);
        const colours=Array.isArray(field.value)&&field.value.length?field.value.map(newColourCard):[newColourCard()];
        const makeInput=(text,value,type='text')=>{const label=document.createElement('label');label.textContent=text;const control=document.createElement(type==='textarea'?'textarea':'input');control.value=value??'';if(type!=='textarea')control.type=type;label.appendChild(control);return [label,control];};
        const tile=(source,labelText,onRemove,isLocal=true)=>{const node=document.createElement('div');node.className='image-tile';if(isLocal){const image=document.createElement('img');image.src=source;image.alt=labelText;image.loading='lazy';node.appendChild(image);}else{const text=document.createElement('span');text.textContent=labelText;text.title=source;node.appendChild(text);}const remove=document.createElement('button');remove.type='button';remove.className='danger';remove.textContent='Remove';remove.onclick=onRemove;node.appendChild(remove);return node;};
        const render=()=>{cards.replaceChildren();colours.forEach((colour,index)=>{
          const card=document.createElement('article');card.className='variant-card';card.dataset.cardKey=colour.cardKey;const title=document.createElement('h4');title.textContent=`Colour ${index+1}`;card.appendChild(title);
          const grid=document.createElement('div');grid.className='dialog-fields';const [nameLabel,name]=makeInput('Colour name',colour.colourName);const [hexLabel,hex]=makeInput('Colour hex (optional)',colour.colourHex);name.oninput=()=>colour.colourName=name.value;hex.oninput=()=>colour.colourHex=hex.value;grid.append(nameLabel,hexLabel);card.appendChild(grid);
          const sizesTitle=document.createElement('strong');sizesTitle.textContent='Sizes & stock';card.appendChild(sizesTitle);const sizes=document.createElement('div');sizes.className='variant-sizes';
          colour.sizes.forEach((size,sizeIndex)=>{const row=document.createElement('div');row.className='variant-size-row';const [sizeLabel,sizeInput]=makeInput('Size',size.size);const [stockLabel,stockInput]=makeInput('Stock',String(size.inventory),'number');stockInput.min='0';stockInput.step='1';sizeInput.oninput=()=>size.size=sizeInput.value;stockInput.oninput=()=>size.inventory=Number(stockInput.value);row.append(sizeLabel,stockLabel);if(colour.sizes.length>1){const remove=document.createElement('button');remove.type='button';remove.className='danger';remove.textContent='Remove size';remove.onclick=()=>{colour.sizes.splice(sizeIndex,1);render();};row.appendChild(remove);}sizes.appendChild(row);});card.appendChild(sizes);
          const addSize=document.createElement('button');addSize.type='button';addSize.className='secondary';addSize.textContent='+ Add size';addSize.onclick=()=>{colour.sizes.push({size:'',inventory:0});render();};card.appendChild(addSize);
          const images=document.createElement('div');images.className='image-tiles';colour.imageUrls.forEach((url,imageIndex)=>images.appendChild(tile(url,`Existing image ${imageIndex+1}`,()=>{colour.imageUrls.splice(imageIndex,1);render();},url.startsWith('/media/product-images/'))));colour.pendingFiles.forEach((entry,imageIndex)=>images.appendChild(tile(entry.preview,`Pending image ${imageIndex+1}`,()=>{colour.pendingFiles.splice(imageIndex,1);render();},true)));card.appendChild(images);
          const uploadLabel=document.createElement('label');uploadLabel.textContent='Choose product images from this PC';const upload=document.createElement('input');upload.type='file';upload.accept='image/jpeg,image/png,image/webp';upload.multiple=true;upload.onchange=async()=>{try{await queueColourFiles(colour,upload.files);render();}catch(cause){byId('admin-dialog-error').textContent=cause.message;}finally{upload.value='';}};uploadLabel.appendChild(upload);card.appendChild(uploadLabel);
          const [urlsLabel,urls]=makeInput('HTTPS image URLs (optional fallback)',colour.httpsDraft,'textarea');urls.oninput=()=>colour.httpsDraft=urls.value;card.appendChild(urlsLabel);
          if(colours.length>1){const removeColour=document.createElement('button');removeColour.type='button';removeColour.className='danger';removeColour.textContent='Remove colour';removeColour.onclick=()=>{colours.splice(index,1);render();};card.appendChild(removeColour);}cards.appendChild(card);
        });};
        addColour.onclick=()=>{colours.push(newColourCard());render();};
        colourVariantsGetter=()=>{const normalized=colours.map(colour=>({cardKey:colour.cardKey,colourName:String(colour.colourName||'').trim(),colourHex:String(colour.colourHex||'').trim()||undefined,imageUrls:colour.imageUrls.map(value=>String(value).trim()).filter(Boolean),httpsDraft:colour.httpsDraft,pendingFiles:[...colour.pendingFiles],sizes:colour.sizes.map(size=>({...(size.id?{id:size.id}:{}),size:String(size.size||'').trim(),inventory:Number(size.inventory)}))}));if(!normalized.length||normalized.some(colour=>!colour.colourName||!colour.sizes.length||colour.sizes.some(size=>!size.size||!Number.isInteger(size.inventory)||size.inventory<0)))throw new Error('Every colour needs a name and valid size/stock rows.');return normalized;};
        render();fieldsRoot.appendChild(section);continue;
      }
      const label=document.createElement('label'); label.textContent=field.label;
      const control=field.type==='textarea'?document.createElement('textarea'):field.type==='select'?document.createElement('select'):document.createElement('input');
      control.name=field.name; control.required=field.required===true;
      if(field.type==='select'){for(const option of field.options||[]){const node=document.createElement('option');node.value=option.value;node.textContent=option.label;control.appendChild(node);}}
      else if(field.type&&field.type!=='textarea')control.type=field.type;
      if(field.accept)control.accept=field.accept; if(field.multiple)control.multiple=true;
      control.value=field.value??'';
      if(field.placeholder)control.placeholder=field.placeholder;
      if(field.minLength)control.minLength=field.minLength;
      if(field.maxLength)control.maxLength=field.maxLength;
      if(field.min!==undefined)control.min=String(field.min);
      if(field.max!==undefined)control.max=String(field.max);
      if(field.step!==undefined)control.step=String(field.step);
      label.appendChild(control);
      if(field.help){const help=document.createElement('small');help.className='field-help';help.textContent=field.help;label.appendChild(help);}
      if(field.type==='file'&&field.previewImages){const preview=document.createElement('div');preview.className='image-preview-grid';label.appendChild(preview);attachImagePreview(control,preview);}
      fieldsRoot.appendChild(label);
    }
    let settled=false;
    const finish=value=>{if(settled)return;settled=true;form.onsubmit=null;byId('admin-dialog-cancel').onclick=null;dialog.oncancel=null;if(dialog.open)dialog.close();resolve(value);};
    form.onsubmit=event=>{event.preventDefault();if(!form.reportValidity())return;try{const values=Object.fromEntries(new FormData(form).entries());for(const field of fields){if(field.type==='file'&&field.multiple)values[field.name]=Array.from(form.elements[field.name]?.files||[]);}if(colourVariantsGetter)values.colourVariants=colourVariantsGetter();finish(values);}catch(cause){byId('admin-dialog-error').textContent=cause.message;}};
    byId('admin-dialog-cancel').onclick=()=>finish(null);
    dialog.oncancel=event=>{event.preventDefault();finish(null);};
    dialog.showModal();
    fieldsRoot.querySelector('input,textarea,select')?.focus();
  });
}

const ADMIN_IMAGE_TYPES=new Set(['image/jpeg','image/png','image/webp']);
function validateAdminImageFile(file,prefix=''){
  if(!(file instanceof File)||file.size<=0)throw new Error(`${prefix}Invalid image file.`);
  if(!ADMIN_IMAGE_TYPES.has(file.type))throw new Error(`${prefix}Unsupported image type. Choose JPG, PNG or WebP.`);
  if(file.size>12*1024*1024)throw new Error(`${prefix}Image exceeds maximum allowed size of 12 MB before optimization.`);
}
function attachImagePreview(control,root){
  const render=()=>{root.replaceChildren();for(const [index,file] of Array.from(control.files||[]).entries()){
    const card=document.createElement('div');card.className='image-preview-card';const image=document.createElement('img');image.alt=`Preview ${file.name}`;const reader=new FileReader();reader.onload=()=>{if(typeof reader.result==='string')image.src=reader.result;};reader.readAsDataURL(file);
    const meta=document.createElement('span');meta.className='image-preview-meta';meta.textContent=`${file.name} - ${Math.max(1,Math.round(file.size/1024))} KB`;const remove=document.createElement('button');remove.type='button';remove.className='image-preview-remove';remove.textContent='Remove';remove.onclick=event=>{event.preventDefault();event.stopPropagation();const transfer=new DataTransfer();Array.from(control.files||[]).forEach((candidate,candidateIndex)=>{if(candidateIndex!==index)transfer.items.add(candidate);});control.files=transfer.files;render();};card.append(image,meta,remove);root.appendChild(card);
  }};control.addEventListener('change',render);render();
}
async function prepareAdminProductImage(file){
  validateAdminImageFile(file);let bitmap;try{bitmap=await createImageBitmap(file,{imageOrientation:'from-image'});}catch{throw new Error(`Image ${file.name} could not be decoded.`);}
  try{const fit=max=>{const scale=Math.min(1,max/Math.max(bitmap.width,bitmap.height));return {width:Math.max(1,Math.round(bitmap.width*scale)),height:Math.max(1,Math.round(bitmap.height*scale))};};let size=fit(1600);let canvas=document.createElement('canvas');canvas.width=size.width;canvas.height=size.height;canvas.getContext('2d').drawImage(bitmap,0,0,size.width,size.height);
    const make=q=>new Promise((resolve,reject)=>canvas.toBlob(blob=>blob?resolve(blob):reject(new Error('Image compression failed.')),'image/webp',q));let blob=await make(.82);for(const q of [.72,.62,.52]){if(blob.size<=350*1024)break;blob=await make(q);}if(blob.size>500*1024){size=fit(1200);canvas=document.createElement('canvas');canvas.width=size.width;canvas.height=size.height;canvas.getContext('2d').drawImage(bitmap,0,0,size.width,size.height);blob=await new Promise((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(new Error('Image compression failed.')),'image/webp',.62));}if(blob.size>500*1024)throw new Error('Image is still too large after compression.');return blob;
  }finally{bitmap.close();}
}
async function blobBase64(blob){const bytes=new Uint8Array(await blob.arrayBuffer());let binary='';for(let i=0;i<bytes.length;i+=0x8000)binary+=String.fromCharCode(...bytes.subarray(i,i+0x8000));return btoa(binary);}
async function uploadAdminProductImages(files,progressOffset=0,progressTotal=null){const urls=[];const total=progressTotal??files.length;for(const [index,file] of (files||[]).entries()){validateAdminImageFile(file);status(`Uploading ${file.name} (${progressOffset+index+1} of ${total})...`);const blob=await prepareAdminProductImage(file);const result=await api('/api/admin/product-images',{method:'POST',body:JSON.stringify({fileName:`${file.name.replace(/\.[^.]+$/,'').slice(0,80)||'product'}.webp`,contentType:'image/webp',dataBase64:await blobBase64(blob)})});urls.push(result.image.url);}return urls;}

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
    {name:'bannerUpload',label:'Store cover image (optional)',type:'file',accept:'image/jpeg,image/png,image/webp'},
    {name:'logoUpload',label:'Store logo (optional)',type:'file',accept:'image/jpeg,image/png,image/webp'},
  ],'Create and activate store'); if(!values)return;
  const payload={ownerUserId:values.ownerUserId,shopName:values.shopName,ownerName:values.ownerName,category:values.category,description:values.description,address:values.address,city:values.city,state:values.state,pincode:values.pincode,businessInformation:values.businessInformation||undefined};
  if(values.bannerUpload instanceof File&&values.bannerUpload.size){payload.bannerImage=(await uploadAdminProductImages([values.bannerUpload]))[0];}
  if(values.logoUpload instanceof File&&values.logoUpload.size){payload.logoImage=(await uploadAdminProductImages([values.logoUpload]))[0];}
  const result=await api('/api/admin/vendors',{method:'POST',body:JSON.stringify(payload)});
  const created=result?.application;
  if(!created?.id||created.status!=='ACTIVE'||created.submittedByUserId!==values.ownerUserId){
    throw new Error('The store response could not be verified. Refresh Shop Applications before trying again.');
  }
  const persisted=(await api('/api/admin/vendors')).applications.find(item=>item.id===created.id&&item.submittedByUserId===values.ownerUserId&&item.status==='ACTIVE');
  if(!persisted){
    throw new Error(`Store ${created.id} was created but could not be verified in Shop Applications. Refresh before retrying.`);
  }
  status(`${persisted.shopName} created and verified ACTIVE ? ${persisted.id}`);
}
async function editStore(button){
  const item=currentVendors.find(store=>store.id===button.dataset.id); if(!item)throw new Error('Store details are no longer available. Refresh and try again.');
  const categories=['Clothing & Fashion','Footwear','Electronics','Home & Living','General Store'];
  const values=await formDialog(`Edit ${item.shopName}`,[
    {name:'shopName',label:'Store name',required:true,value:item.shopName||'',maxLength:100},
    {name:'ownerName',label:'Owner / contact name',required:true,value:item.ownerName||'',maxLength:80},
    {name:'category',label:'Category',type:'select',required:true,value:item.category||categories[0],options:categories.map(value=>({value,label:value}))},
    {name:'description',label:'Store description',type:'textarea',required:true,value:item.description||'',maxLength:1000},
    {name:'address',label:'Store address',type:'textarea',required:true,value:item.address||'',maxLength:250},
    {name:'city',label:'City',required:true,value:item.city||'Neemuch',maxLength:80},
    {name:'state',label:'State',required:true,value:item.state||'Madhya Pradesh',maxLength:80},
    {name:'pincode',label:'Pincode',required:true,value:item.pincode||'458441',maxLength:6},
    {name:'businessInformation',label:'Business information (optional)',type:'textarea',value:item.businessInformation||'',maxLength:1000},
    {name:'bannerUpload',label:'Replace store cover (optional)',type:'file',accept:'image/jpeg,image/png,image/webp'},
    {name:'logoUpload',label:'Replace store logo (optional)',type:'file',accept:'image/jpeg,image/png,image/webp'},
  ],'Save Store Changes'); if(!values)return;
  const payload={shopName:values.shopName,ownerName:values.ownerName,category:values.category,description:values.description,address:values.address,city:values.city,state:values.state,pincode:values.pincode,businessInformation:values.businessInformation||undefined};
  if(values.bannerUpload instanceof File&&values.bannerUpload.size){payload.bannerImage=(await uploadAdminProductImages([values.bannerUpload]))[0];}
  if(values.logoUpload instanceof File&&values.logoUpload.size){payload.logoImage=(await uploadAdminProductImages([values.logoUpload]))[0];}
  await api(`/api/admin/vendors/${encodeURIComponent(item.id)}/details`,{method:'PATCH',body:JSON.stringify(payload)});
  status(`${values.shopName} store details updated.`);
}

const PRODUCT_DEPARTMENTS=['men','women','kids','unisex'];
const PRODUCT_CATEGORIES=['Clothing & Fashion','Footwear','Accessories','Beauty & Personal Care','Electronics','Home & Living','General Store'];
const DELIVERY_OPTIONS=[{value:'normal',label:'Site-wide: Normal Mon-Fri; Normal + Express Sat-Sun'}];

function downloadProductCsvTemplate(){
  const header=['name','description','brand','department','category','subcategory','deliveryType','price','originalPrice','variants','colourName','colourHex','imageFile','imageUrls'];
  const sample=['Campus Sports Shoes','Sports shoes','Campus','unisex','Footwear','','normal','1720','1720','6:5, 7:5, 8:5, 9:5, 10:5','Multi Color (White/Blue/Green)','','product1.jpg',''];
  const quote=value=>`"${String(value).replaceAll('"','""')}"`;const blob=new Blob([[header,sample].map(row=>row.map(quote).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='vibe4you-product-import-template.csv';link.click();URL.revokeObjectURL(link.href);
}
function parseCsv(text){
  const rows=[];let row=[];let field='';let quoted=false;for(let i=0;i<text.length;i++){const ch=text[i];if(quoted){if(ch==='"'&&text[i+1]==='"'){field+='"';i++;}else if(ch==='"')quoted=false;else field+=ch;continue;}if(ch==='"'){quoted=true;continue;}if(ch===','){row.push(field);field='';continue;}if(ch==='\n'){row.push(field.replace(/\r$/,''));rows.push(row);row=[];field='';continue;}field+=ch;}if(quoted)throw new Error('CSV has an unterminated quoted field.');if(field||row.length){row.push(field.replace(/\r$/,''));rows.push(row);}return rows.filter(candidate=>candidate.some(value=>value.trim()));
}
function csvImageRequirements(text){
  const rows=parseCsv(text);if(rows.length<2)throw new Error('CSV needs a header row and at least one product.');const headers=rows[0].map((value,index)=>(index===0?value.replace(/^\uFEFF/,''):value).trim());if(new Set(headers).size!==headers.length)throw new Error('CSV headers must be unique.');
  const required=['name','description','department','category','price','variants','colourName'];for(const key of required)if(!headers.includes(key))throw new Error(`CSV is missing required column: ${key}`);if(!headers.includes('imageFile')&&!headers.includes('imageUrls'))throw new Error('CSV requires imageFile or imageUrls.');const requirements=[];let productRows=0;
  for(const row of rows.slice(1)){if(!row.some(value=>value.trim()))continue;productRows+=1;const values=Object.fromEntries(headers.map((key,index)=>[key,(row[index]??'').trim()]));const imageFile=values.imageFile||'';const direct=(values.imageUrls||'').split('|').map(value=>value.trim()).filter(Boolean);if(imageFile){if(imageFile.includes('/')||imageFile.includes('\\'))throw new Error(`Row ${productRows}: Image file "${imageFile}" is invalid.`);requirements.push({row:productRows,fileName:imageFile});}else if(!direct.length)throw new Error(`Row ${productRows}: At least one product image is required.`);}
  if(!productRows)throw new Error('CSV needs at least one product row.');if(productRows>100)throw new Error('Upload a maximum of 100 products at a time.');return {productRows,requirements};
}
function selectedImageMap(files){const map=new Map();for(const file of files||[]){if(map.has(file.name))throw new Error(`More than one selected image is named "${file.name}".`);map.set(file.name,file);}return map;}
async function bulkUploadStoreProducts(){
  const applications=(await api('/api/admin/vendors')).applications.filter(item=>item.status==='ACTIVE');if(!applications.length)throw new Error('There are no active shops available for product import.');
  const values=await formDialog('Bulk upload products',[
    {name:'applicationId',label:'Publish products for',type:'select',required:true,options:applications.map(item=>({value:item.id,label:`${item.shopName} - ${item.ownerName}`}))},
    {name:'csv',label:'Product CSV',type:'file',accept:'.csv,text/csv',required:true,help:'Use imageFile values such as product1.jpg. Keep deliveryType as normal; the site automatically offers Normal Mon-Fri and Normal + Express Sat-Sun for every product.'},
    {name:'imageFiles',label:'Select the local product images referenced by the CSV',type:'file',accept:'image/jpeg,image/png,image/webp',multiple:true,previewImages:true,help:'Filenames are matched exactly to imageFile. Images upload automatically before products are published.'},
  ],'Review import');if(!values)return;
  const csvFile=values.csv;if(!(csvFile instanceof File)||!csvFile.size)throw new Error('Choose a CSV file.');if(csvFile.size>1024*1024)throw new Error('CSV must be 1 MB or smaller.');const csvText=await csvFile.text();const plan=csvImageRequirements(csvText);const selected=selectedImageMap(values.imageFiles||[]);const requiredFiles=new Map();
  for(const requirement of plan.requirements){const file=selected.get(requirement.fileName);if(!file)throw new Error(`Row ${requirement.row}: Image file "${requirement.fileName}" was not selected.`);validateAdminImageFile(file,`Row ${requirement.row}: `);requiredFiles.set(requirement.fileName,file);}
  const selectedShop=applications.find(item=>item.id===values.applicationId);const approval=await formDialog(`Publish ${plan.productRows} products to ${selectedShop?.shopName||'selected shop'}?`,[],`Upload images & publish ${plan.productRows}`);if(!approval)return;
  const images={};let uploaded=0;for(const [fileName,file] of requiredFiles){status(`Uploading ${fileName} (${uploaded+1} of ${requiredFiles.size})...`);images[fileName]=(await uploadAdminProductImages([file],uploaded,requiredFiles.size))[0];uploaded+=1;}
  const result=await api('/api/admin/shop-products/bulk',{method:'POST',body:JSON.stringify({applicationId:values.applicationId,csvText,images})});status(`${result.created} products published successfully with ${requiredFiles.size} local image${requiredFiles.size===1?'':'s'}.`);
}
async function createStoreProduct(){
  const applications=(await api('/api/admin/vendors')).applications.filter(item=>item.status==='ACTIVE');if(!applications.length)throw new Error('There are no active shops available for product creation.');
  const values=await formDialog('Add product for local store',[
    {name:'applicationId',label:'Store',type:'select',required:true,options:applications.map(item=>({value:item.id,label:item.shopName}))},
    {name:'name',label:'Product name',required:true,maxLength:140},{name:'description',label:'Product description',type:'textarea',required:true,maxLength:2000},{name:'brand',label:'Brand (optional)',maxLength:100},
    {name:'department',label:'Department',type:'select',required:true,value:'unisex',options:PRODUCT_DEPARTMENTS.map(value=>({value,label:value}))},{name:'category',label:'Category',type:'select',required:true,value:'Clothing & Fashion',options:PRODUCT_CATEGORIES.map(value=>({value,label:value}))},{name:'subcategory',label:'Subcategory (optional; inferred when clear)',maxLength:100},{name:'deliveryType',label:'Delivery schedule',type:'select',required:true,value:'normal',options:DELIVERY_OPTIONS},
    {name:'price',label:'Selling price in rupees',type:'number',required:true,min:1,step:'0.01'},{name:'originalPrice',label:'Original/MRP price in rupees',type:'number',min:1,step:'0.01'},
    {name:'colourVariants',label:'Colours & Variants',type:'colourVariants'},
  ],'Upload images & publish');if(!values)return;
  const price=Number(values.price),originalPrice=Number(values.originalPrice||values.price);if(!Number.isFinite(price)||price<1||!Number.isFinite(originalPrice)||originalPrice<price)throw new Error('Enter valid selling and original prices.');
  const colourVariants=await uploadColourVariantImages(values.colourVariants);
  const payload={applicationId:values.applicationId,name:values.name,description:values.description,brand:values.brand||undefined,department:values.department,category:values.category,subcategory:values.subcategory||undefined,deliveryType:values.deliveryType,pricePaise:Math.round(price*100),originalPricePaise:Math.round(originalPrice*100),colourVariants,attributes:{}};
  await api('/api/admin/shop-products',{method:'POST',body:JSON.stringify(payload)});status(`${values.name} published with ${colourVariants.length} colour${colourVariants.length===1?'':'s'}.`);
}
async function editStoreProduct(button){
  const item=currentShopProducts.find(product=>product.id===button.dataset.id);if(!item)throw new Error('Product details are no longer available. Refresh and try again.');
  const live=(await api(`/api/admin/inventory?low=0&q=${encodeURIComponent(item.id)}`)).inventory||[];const liveById=new Map(live.map(row=>[row.variantId,Number(row.stock)]));
  const colourSource=(Array.isArray(item.colourVariants)&&item.colourVariants.length?item.colourVariants:[{colourName:item.colourName||'Multi',colourHex:item.colourHex||'',imageUrls:item.imageUrls||[],sizes:item.variants||[]}]).map(colour=>({...colour,sizes:(colour.sizes||[]).map(size=>({...size,inventory:liveById.has(size.id)?liveById.get(size.id):size.inventory}))}));
  const values=await formDialog('Edit product details',[
    {name:'name',label:'Product name',required:true,value:item.name||'',maxLength:140},{name:'description',label:'Description',type:'textarea',required:true,value:item.description||'',maxLength:2000},{name:'brand',label:'Brand (optional)',value:item.brand||'',maxLength:100},
    {name:'department',label:'Department',type:'select',required:true,value:PRODUCT_DEPARTMENTS.includes(item.department)?item.department:'unisex',options:PRODUCT_DEPARTMENTS.map(value=>({value,label:value}))},{name:'category',label:'Category',type:'select',required:true,value:PRODUCT_CATEGORIES.includes(item.category)?item.category:'Clothing & Fashion',options:PRODUCT_CATEGORIES.map(value=>({value,label:value}))},{name:'subcategory',label:'Subcategory (optional; inferred when clear)',value:item.subcategory||item.attributes?.subcategory||'',maxLength:100},{name:'deliveryType',label:'Delivery schedule',type:'select',required:true,value:'normal',options:DELIVERY_OPTIONS},
    {name:'price',label:'Selling price in rupees',type:'number',required:true,value:(item.pricePaise/100).toFixed(2),min:1,step:'0.01'},{name:'original',label:'Original/MRP price in rupees',type:'number',required:true,value:(item.originalPricePaise/100).toFixed(2),min:1,step:'0.01'},
    {name:'colourVariants',label:'Colours & Variants',type:'colourVariants',value:colourSource},
  ],'Save all changes');if(!values)return;
  const price=Number(values.price),original=Number(values.original);if(!Number.isFinite(price)||price<1||!Number.isFinite(original)||original<price)throw new Error('Enter valid selling and original prices.');
  const colourVariants=await uploadColourVariantImages(values.colourVariants);
  const payload={name:values.name,description:values.description,brand:values.brand||undefined,department:values.department,category:values.category,subcategory:values.subcategory||undefined,deliveryType:values.deliveryType,pricePaise:Math.round(price*100),originalPricePaise:Math.round(original*100),colourVariants,attributes:item.attributes||{}};
  const wasPublished=item.status==='PUBLISHED';let unpublished=false,updatedProduct=null;
  try{if(wasPublished){await api(`/api/admin/shop-products/${encodeURIComponent(item.id)}`,{method:'PATCH',body:JSON.stringify({status:'APPROVED'})});unpublished=true;}const result=await api(`/api/admin/shop-products/${encodeURIComponent(item.id)}/details`,{method:'PATCH',body:JSON.stringify(payload)});updatedProduct=result.product;if(wasPublished){await api(`/api/admin/shop-products/${encodeURIComponent(item.id)}`,{method:'PATCH',body:JSON.stringify({status:'PUBLISHED'})});unpublished=false;}}catch(cause){if(unpublished){try{await api(`/api/admin/shop-products/${encodeURIComponent(item.id)}`,{method:'PATCH',body:JSON.stringify({status:'PUBLISHED'})});}catch{}}throw cause;}
  if(wasPublished&&updatedProduct){const current=(await api(`/api/admin/inventory?low=0&q=${encodeURIComponent(item.id)}`)).inventory||[];for(const variant of updatedProduct.variants||[]){const row=current.find(record=>record.variantId===variant.id);if(!row)throw new Error(`Inventory row ${variant.id} is unavailable after product update.`);const delta=Number(variant.inventory)-Number(row.stock);if(delta)await api(`/api/admin/inventory/${encodeURIComponent(variant.id)}`,{method:'PATCH',body:JSON.stringify({delta})});}}
  status('All product colours, images, sizes, stock and details updated.');
}
async function reasonFor(title){const values=await formDialog(title,[{name:'reason',label:'Reason',type:'textarea',required:true,maxLength:1000}],'Continue');return values?.reason||null;}
async function codCollectionMethodFor(){
  const values=await formDialog('Mark COD payment as paid',[{name:'collectionMethod',label:'Money was actually collected via',type:'select',required:true,options:[{value:'cash',label:'Cash'},{value:'upi_at_delivery',label:'UPI at delivery'}]}],'Mark as Paid');
  return values?.collectionMethod||null;
}
async function cancellationReasonFor(){
  const options=['Product unavailable','Size/color unavailable','Store unable to fulfil','Customer requested cancellation','Duplicate order','Delivery not serviceable','Other'].map(value=>({value,label:value}));
  const values=await formDialog('Cancel order',[{name:'reasonType',label:'Cancellation reason',type:'select',required:true,options},{name:'details',label:'Additional details (required for Other)',type:'textarea',maxLength:500}],'Cancel Order');
  if(!values)return null;
  const type=String(values.reasonType||'').trim(),details=String(values.details||'').trim();
  if(type==='Other'&&!details)throw new Error('Enter the cancellation reason in Additional details.');
  return details&&type!=='Other'?`${type}: ${details}`:(details||type);
}
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
    if(action==='edit-store') await editStore(button);
    if(action==='create-shop-product') await createStoreProduct();
    if(action==='bulk-shop-products') await bulkUploadStoreProducts();
    if(action==='download-product-template') downloadProductCsvTemplate();
    if(action==='edit-shop-product') await editStoreProduct(button);
    if(action==='mark-cod-paid') { const collectionMethod=await codCollectionMethodFor(); if(!collectionMethod)return; await api(`/api/admin/orders/${encodeURIComponent(button.dataset.id)}/payment`,{method:'PATCH',body:JSON.stringify({collectionMethod})}); status('COD payment marked paid after collection. Order confirmation remains separate.'); }
    if(action==='order-status') { const nextStatus=button.dataset.value; let reason=null; if(nextStatus==='cancelled'){reason=await cancellationReasonFor();if(!reason)return;} await api(`/api/admin/orders/${encodeURIComponent(button.dataset.id)}/status`,{method:'PATCH',body:JSON.stringify({status:nextStatus,reason})}); status(nextStatus==='cancelled'?'Order cancelled and the reason is visible to the customer.':'Order status updated.'); }
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
    const searchLabels={orders:'orders, customers or products',vendors:'shops, owners or contact details','shop-products':'products, brands or shops','shop-product-requests':'products, shops or requests',inventory:'products, variants or sizes',customers:'customers, email or mobile','payment-alerts':'alerts, orders or payment references',audit:'audit actions, targets or results'};
    if(searchLabels[tab])byId('search').placeholder=`Search ${searchLabels[tab]}`;
    byId('search-form').hidden=!['orders','vendors','shop-products','shop-product-requests','inventory','customers','payment-alerts','audit'].includes(tab);
    if(tab==='orders') return renderOrders((await api(`/api/admin/orders?q=${query}`)).orders);
    if(tab==='vendors') return renderVendors((await api('/api/admin/vendors')).applications);
    if(tab==='shop-products'){
      const [productResult,vendorResult]=await Promise.all([api('/api/admin/shop-products'),api('/api/admin/vendors')]);
      currentShopProducts=productResult.products; shopProductStores=vendorResult.applications;
      return renderShopProducts(currentShopProducts,shopProductStores);
    }
    if(tab==='shop-product-requests') return renderShopProductRequests((await api('/api/admin/shop-product-requests')).requests);
    if(tab==='inventory') return renderInventory((await api(`/api/admin/inventory?low=${adminFilters.inventory.stock==='low'?'1':'0'}&q=${query}`)).inventory);
    if(tab==='customers') return renderCustomers((await api(`/api/admin/customers?q=${query}`)).customers);
    if(tab==='payment-alerts') return renderPaymentAlerts((await api('/api/admin/payment-alerts')).alerts);
    if(tab==='system') return renderSystem((await api('/api/admin/system')).system);
    if(tab==='audit') return renderAudit((await api('/api/admin/audit')).audit);
  } catch(cause) { byId('content').innerHTML=''; error(cause.message); if(cause.message.includes('authentication')) showLogin(); }
}

function orderActionLabel(value){return ({placed:'Confirm Stock',confirmed:'Confirm Order',preparing:'Mark Preparing',packed:'Mark Packed',out_for_delivery:'Out for Delivery',delivered:'Mark Delivered',cancelled:'Cancel Order'})[value]||value.replaceAll('_',' ');}
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
function adminSearch(){return byId('search').value.trim().toLowerCase();}
function matchesAdminSearch(item,fields){const q=adminSearch();return !q||fields.some(field=>String(item?.[field]??'').toLowerCase().includes(q));}
function adminFilterBar(label,controls,shown,total){return `<section class="order-filters" aria-label="${escapeText(label)}">${controls.join('')}<div class="order-filter-summary"><span><strong>${shown}</strong> of ${total}</span></div></section>`;}
function adminSelect(label,key,values,selected){return `<label>${escapeText(label)}<select data-admin-filter="${escapeText(key)}">${filterOptions(values,selected)}</select></label>`;}
function renderOrders(orders){currentOrders=Array.isArray(orders)?orders:[];renderOrdersView();}
function orderItemMarkup(item){
  const store=item.storeName||item.storeId||'Vibe4You';
  const product=item.productName||item.name||item.productId||'Product';
  const variant=[item.size?`Size ${item.size}`:'',item.colourName||item.colour?`Color ${item.colourName||item.colour}`:''].filter(Boolean).join(' · ');
  return `<div class="order-item"><div><small>Store</small><strong>${escapeText(store)}</strong></div><div><small>Product</small><strong>${escapeText(product)}</strong><span>${escapeText(variant||'Variant not recorded')}</span></div><div><small>Quantity</small><strong>${escapeText(item.quantity||0)}</strong></div><div><small>Line total</small><strong>₹${escapeText(item.lineTotal??'-')}</strong></div></div>`;
}
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
  const filters=`<section class="order-filters" aria-label="Order filters"><label>Order status<select data-order-filter="status">${filterOptions(orderStatuses,orderFilters.status)}</select></label><label>Payment status<select data-order-filter="payment">${filterOptions(paymentStatuses,orderFilters.payment)}</select></label><label>Fulfillment<select data-order-filter="fulfillment"><option value="all"${orderFilters.fulfillment==='all'?' selected':''}>All</option><option value="required"${orderFilters.fulfillment==='required'?' selected':''}>Customer orders</option><option value="test"${orderFilters.fulfillment==='test'?' selected':''}>Payment tests</option></select></label><div class="order-filter-summary"><span><strong>${filtered.length}</strong> of ${currentOrders.length} orders</span><button class="secondary" data-action="clear-order-filters">Clear filters</button></div></section>`;
  const cards=filtered.map(order=>{
    const paymentTest=order.isPaymentTestOrder===true||order.fulfillmentRequired===false;
    const tone=statusTone(order.status);
    const address=order.address||{};
    const cancellation=order.cancellationReason?`<div class="order-cancellation"><strong>Cancellation reason</strong><span>${escapeText(order.cancellationReason)}</span></div>`:'';
    const collectButton=!paymentTest&&order.paymentMethod==='cod'&&order.paymentStatus==='pending'&&order.status!=='cancelled'?`<button class="success" data-action="mark-cod-paid" data-id="${escapeText(order.id)}">Mark as Paid</button>`:'';
    const actions=paymentTest?'<p class="payment-test-note">Payment validation record only. Do not pack, dispatch, deliver, or adjust fashion inventory.</p>':`<div class="actions">${collectButton}${orderActions(order).map(next=>`<button class="${next==='cancelled'?'danger':'success'}" data-action="order-status" data-id="${escapeText(order.id)}" data-value="${next}">${escapeText(orderActionLabel(next))}</button>`).join('')}</div>`;
    return `<article class="card order-card order-tone-${tone}">${paymentTest?'<div class="payment-test-banner"><strong>TEST</strong><strong>NO FULFILLMENT REQUIRED</strong></div>':''}<div class="order-heading"><div><small>Order reference</small><h3>${escapeText(order.id)}</h3><span class="muted">${escapeText(order.createdAt||'')}</span></div><div class="order-heading-status">${statusBadge(order.status)}<strong>₹${escapeText(order.grandTotal)}</strong></div></div><div class="order-customer"><div><small>Customer</small><strong>${escapeText(address.name||'-')}</strong><span>${escapeText(address.phone||'-')}</span></div><div><small>Delivery address</small><strong>${escapeText(address.street||'-')}</strong><span>${escapeText([address.city,address.state,address.pincode].filter(Boolean).join(', '))}</span></div><div><small>Payment</small>${statusBadge(order.paymentStatus)}<span>${escapeText(String(order.paymentMethod||'').toUpperCase())}</span>${order.paymentCollectionMethod?`<span>${escapeText(order.paymentCollectionMethod==='upi_at_delivery'?'UPI at delivery':'Cash')} · ${escapeText(order.paymentCollectedAt||'')}</span>`:''}</div></div><div class="order-items"><h4>Products</h4>${(order.items||[]).map(orderItemMarkup).join('')||'<p class="muted">No item details recorded.</p>'}</div>${cancellation}${actions}</article>`;
  }).join('');
  byId('content').innerHTML=`<h2>Recent orders</h2>${filters}<div class="grid">${cards||'<p>No orders match the selected filters.</p>'}</div>`;
}
function applicationTransitions(status){return {SUBMITTED:['UNDER_REVIEW'],UNDER_REVIEW:['APPROVED','REJECTED'],APPROVED:['ACTIVE'],ACTIVE:['SUSPENDED'],SUSPENDED:['ACTIVE']}[status]||[];}
function productTransitions(status){return {SUBMITTED:['UNDER_REVIEW'],UNDER_REVIEW:['APPROVED','REJECTED'],APPROVED:['PUBLISHED'],PUBLISHED:['APPROVED']}[status]||[];}
function productRequestTransitions(status){return {SUBMITTED:['UNDER_REVIEW'],UNDER_REVIEW:['APPROVED','REJECTED']}[status]||[];}
function renderVendors(items){
  currentVendors=Array.isArray(items)?items:[]; const f=adminFilters.vendors;
  const filtered=currentVendors.filter(item=>matchesAdminSearch(item,['shopName','ownerName','registeredEmail','registeredMobile','address','city','pincode','description','category','id'])&&(f.status==='all'||item.status===f.status)&&(f.category==='all'||item.category===f.category));
  const controls=[adminSelect('Status','status',currentVendors.map(item=>item.status),f.status),adminSelect('Category','category',currentVendors.map(item=>item.category),f.category)];
  byId('content').innerHTML=`<h2>Shop applications</h2><div class="actions"><button class="success" data-action="create-store">Create Local Store</button></div>${adminFilterBar('Shop application filters',controls,filtered.length,currentVendors.length)}<div class="grid">${filtered.map(item=>`<article class="card"><h3>${escapeText(item.shopName)}</h3><small>${escapeText(item.id)}</small><p>${escapeText(item.ownerName)} / ${escapeText(item.registeredEmail)} / ${escapeText(item.registeredMobile)}</p><p class="muted">${escapeText(item.address)}, ${escapeText(item.city)} ${escapeText(item.pincode)} - ${escapeText(item.description)}</p>${item.rejectionReason?`<p class="error">${escapeText(item.rejectionReason)}</p>`:''}<strong>${escapeText(item.status)}</strong><div class="actions"><button data-action="edit-store" data-id="${escapeText(item.id)}">Edit Store</button>${applicationTransitions(item.status).map(status=>`<button class="${['REJECTED','SUSPENDED'].includes(status)?'danger':'success'}" data-action="vendor" data-id="${escapeText(item.id)}" data-value="${status}">${escapeText(status.replaceAll('_',' '))}</button>`).join('')}</div></article>`).join('')||'<p>No shop applications match the current search and filters.</p>'}</div>`;
}
function renderShopProducts(items,applications=shopProductStores){
  const storeMap=new Map(applications.map(item=>[item.id,item.shopName||item.id]));
  const storeIds=[...new Set(items.map(item=>item.applicationId))];
  if(shopProductFilter!=='all'&&!storeIds.includes(shopProductFilter))shopProductFilter='all';
  const stores=storeIds.map(id=>({id,name:storeMap.get(id)||id})).sort((a,b)=>a.name.localeCompare(b.name));
  const f=adminFilters['shop-products'];
  const filtered=items.filter(item=>(shopProductFilter==='all'||item.applicationId===shopProductFilter)&&(f.status==='all'||item.status===f.status)&&(f.category==='all'||item.category===f.category)&&matchesAdminSearch({...item,storeName:storeMap.get(item.applicationId)},['name','brand','category','department','description','id','applicationId','storeName']));
  const options=['<option value="all"'+(shopProductFilter==='all'?' selected':'')+'>All Shops</option>',...stores.map(store=>`<option value="${escapeText(store.id)}"${shopProductFilter===store.id?' selected':''}>${escapeText(store.name)}</option>`)].join('');
  const extra=[adminSelect('Status','status',items.map(item=>item.status),f.status),adminSelect('Category','category',items.map(item=>item.category),f.category)].join('');
  byId('content').innerHTML=`<h2>Shop product submissions</h2><div class="actions"><button class="success" data-action="create-shop-product">Add Product for Local Store</button><button class="success" data-action="bulk-shop-products">Bulk Upload CSV</button><button class="secondary" data-action="download-product-template">Download CSV Template</button></div><section class="order-filters" aria-label="Shop product filters"><label>Shop<select data-shop-product-filter>${options}</select></label>${extra}<div class="order-filter-summary"><span><strong>${filtered.length}</strong> of ${items.length} products</span></div></section><div class="grid">${filtered.map(item=>`<article class="card"><h3>${escapeText(item.name)}</h3><small>${escapeText(storeMap.get(item.applicationId)||item.applicationId)} · ${escapeText(item.id)}</small><p>${escapeText(item.category)} · ₹${escapeText((item.pricePaise/100).toFixed(2))} · total stock ${escapeText(item.inventory)}</p><p>${(item.variants||[]).map(variant=>`${escapeText(variant.size)}: <strong>${escapeText(variant.inventory)}</strong>`).join(' · ')}</p><p class="muted">${escapeText(item.description)}</p>${item.rejectionReason?`<p class="error">${escapeText(item.rejectionReason)}</p>`:''}<strong>${escapeText(item.status)}</strong><div class="actions"><button data-action="edit-shop-product" data-id="${escapeText(item.id)}" data-name="${escapeText(item.name)}" data-description="${escapeText(item.description)}" data-price="${escapeText((item.pricePaise/100).toFixed(2))}" data-original="${escapeText((item.originalPricePaise/100).toFixed(2))}">Edit Details</button>${productTransitions(item.status).map(status=>`<button class="${status==='REJECTED'?'danger':'success'}" data-action="shop-product" data-id="${escapeText(item.id)}" data-value="${status}">${escapeText(status==='APPROVED'&&item.status==='PUBLISHED'?'UNPUBLISH':status.replaceAll('_',' '))}</button>`).join('')}</div></article>`).join('')||'<p>No products match the current search and filters.</p>'}</div>`;
}
function renderShopProductRequests(items){
  const all=Array.isArray(items)?items:[]; const f=adminFilters['shop-product-requests'];
  const filtered=all.filter(item=>matchesAdminSearch(item,['productName','productId','shopName','applicationId','action','status'])&&(f.status==='all'||item.status===f.status)&&(f.action==='all'||item.action===f.action));
  const controls=[adminSelect('Status','status',all.map(item=>item.status),f.status),adminSelect('Request type','action',all.map(item=>item.action),f.action)];
  byId('content').innerHTML=`<h2>Product change requests</h2>${adminFilterBar('Product change request filters',controls,filtered.length,all.length)}<div class="grid">${filtered.map(item=>{const proposed=item.proposedProduct?JSON.stringify(item.proposedProduct,null,2):'';return `<article class="card"><h3>${escapeText(item.productName||item.productId)}</h3><p>${escapeText(item.shopName||item.applicationId)} / ${escapeText(item.action)}</p>${proposed?`<pre>${escapeText(proposed)}</pre>`:'<p class="muted">Seller requested this product be unpublished.</p>'}${item.rejectionReason?`<p class="error">${escapeText(item.rejectionReason)}</p>`:''}<strong>${escapeText(item.status)}</strong><div class="actions">${productRequestTransitions(item.status).map(status=>`<button class="${status==='REJECTED'?'danger':'success'}" data-action="shop-product-request" data-id="${escapeText(item.id)}" data-value="${status}">${escapeText(status.replaceAll('_',' '))}</button>`).join('')}</div></article>`;}).join('')||'<p>No product change requests match the current search and filters.</p>'}</div>`;
}
function renderInventory(items){
  const all=Array.isArray(items)?items:[]; const f=adminFilters.inventory;
  const filtered=all.filter(item=>matchesAdminSearch(item,['productName','size','colour','variantId'])&&(f.stock==='all'||Number(item.stock)<=5));
  const controls=[`<label>Stock<select data-admin-filter="stock"><option value="low"${f.stock==='low'?' selected':''}>Low stock (5 or fewer)</option><option value="all"${f.stock==='all'?' selected':''}>All stock</option></select></label>`];
  byId('content').innerHTML=`<h2>Inventory</h2>${adminFilterBar('Inventory filters',controls,filtered.length,all.length)}<table><thead><tr><th>Product</th><th>Variant</th><th>Stock</th><th>Action</th></tr></thead><tbody>${filtered.map(item=>`<tr><td>${escapeText(item.productName)}</td><td>${escapeText(item.size)} / ${escapeText(item.colour)}<br><small>${escapeText(item.variantId)}</small></td><td><strong>${escapeText(item.stock)}</strong></td><td><button data-action="inventory" data-id="${escapeText(item.variantId)}">Adjust</button></td></tr>`).join('')}</tbody></table>${filtered.length?'':'<p>No inventory matches the current search and filters.</p>'}`;
}
function renderCustomers(items){
  const all=Array.isArray(items)?items:[]; const f=adminFilters.customers;
  const filtered=all.filter(item=>matchesAdminSearch(item,['name','email','phone','id'])&&(f.status==='all'||(f.status==='active'&&item.is_active)||(f.status==='disabled'&&!item.is_active)));
  const controls=[`<label>Status<select data-admin-filter="status"><option value="all"${f.status==='all'?' selected':''}>All</option><option value="active"${f.status==='active'?' selected':''}>Active</option><option value="disabled"${f.status==='disabled'?' selected':''}>Disabled</option></select></label>`];
  byId('content').innerHTML=`<h2>Customers</h2><div class="actions"><button class="success" data-action="create-owner">Create Store Owner Account</button></div>${adminFilterBar('Customer filters',controls,filtered.length,all.length)}<table><thead><tr><th>Customer</th><th>Contact</th><th>Status</th><th>Action</th></tr></thead><tbody>${filtered.map(item=>`<tr><td>${escapeText(item.name)}<br><small>${escapeText(item.id)}</small></td><td>${escapeText(item.email)}<br>${escapeText(item.phone)}</td><td>${item.is_active?'Active':'Disabled'}</td><td><div class="actions"><button data-action="reset-customer-password" data-id="${escapeText(item.id)}">Reset Password</button><button class="${item.is_active?'danger':'success'}" data-action="customer" data-id="${escapeText(item.id)}" data-value="${item.is_active?'false':'true'}">${item.is_active?'Disable':'Enable'}</button></div></td></tr>`).join('')}</tbody></table>${filtered.length?'':'<p>No customers match the current search and filters.</p>'}`;
}
function renderPaymentAlerts(items){
  const all=Array.isArray(items)?items:[]; const f=adminFilters['payment-alerts'];
  const filtered=all.filter(item=>matchesAdminSearch(item,['type','entityId','styleDashOrderId','razorpayPaymentId','status','recordedAt'])&&(f.status==='all'||item.status===f.status)&&(f.type==='all'||item.type===f.type));
  const controls=[adminSelect('Status','status',all.map(item=>item.status),f.status),adminSelect('Event','type',all.map(item=>item.type),f.type)];
  byId('content').innerHTML=`<h2>Payment alerts requiring attention</h2>${adminFilterBar('Payment alert filters',controls,filtered.length,all.length)}<table><thead><tr><th>Time</th><th>Event</th><th>Vibe4You order</th><th>Payment reference</th><th>Status</th></tr></thead><tbody>${filtered.map(item=>`<tr><td>${escapeText(item.recordedAt)}</td><td><strong>${escapeText(item.type)}</strong><br><small>${escapeText(item.entityId)}</small></td><td>${escapeText(item.styleDashOrderId||'Unmatched')}</td><td>${escapeText(item.razorpayPaymentId)}</td><td>${escapeText(item.status)}</td></tr>`).join('')}</tbody></table>${filtered.length?'':'<p>No payment alerts match the current search and filters.</p>'}`;
}
function renderSystem(system){byId('content').innerHTML=`<h2>System</h2><div class="facts"><div class="fact"><small>Admin service</small><strong>${escapeText(system.adminService)}</strong></div><div class="fact"><small>Database</small><strong>${escapeText(system.database.database)}</strong><small>Migration ${escapeText(system.database.migrationVersion)}</small></div><div class="fact"><small>Public service</small><strong>${escapeText(system.publicService.status)}</strong></div><div class="fact"><small>Payment mode</small><strong>${escapeText(system.paymentMode)}</strong></div><div class="fact"><small>Latest backup</small><strong>${escapeText(system.latestBackup||'None')}</strong></div></div>`;}
function renderAudit(items){
  const all=Array.isArray(items)?items:[]; const f=adminFilters.audit;
  const filtered=all.filter(item=>matchesAdminSearch(item,['created_at','action','target_type','target_id','result'])&&(f.result==='all'||item.result===f.result)&&(f.target==='all'||item.target_type===f.target)&&(f.action==='all'||item.action===f.action));
  const controls=[adminSelect('Result','result',all.map(item=>item.result),f.result),adminSelect('Target','target',all.map(item=>item.target_type),f.target),adminSelect('Action','action',all.map(item=>item.action),f.action)];
  byId('content').innerHTML=`<h2>Administrator audit</h2>${adminFilterBar('Audit filters',controls,filtered.length,all.length)}<table><thead><tr><th>Time</th><th>Action</th><th>Target</th><th>Result</th></tr></thead><tbody>${filtered.map(item=>`<tr><td>${escapeText(item.created_at)}</td><td>${escapeText(item.action)}</td><td>${escapeText(item.target_type)} ${escapeText(item.target_id)}</td><td>${escapeText(item.result)}</td></tr>`).join('')}</tbody></table>${filtered.length?'':'<p>No audit entries match the current search and filters.</p>'}`;
}

api('/api/admin/me').then(result=>{csrfToken=result.csrfToken;showApp(result.admin);}).catch(showLogin);
