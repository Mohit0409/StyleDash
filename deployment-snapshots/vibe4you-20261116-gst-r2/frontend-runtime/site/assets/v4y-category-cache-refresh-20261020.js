/* One-time refresh for Vibe4You 2026-10-20 taxonomy update.
   Restore immutable cached chunks only on relevant route; no order/payment operations. */
(()=>{"use strict";
const key="v4y-category-18-20261020";
const sources=["/assets/categories-C-uMYXyt-v4y044-pr150-review-r5.js","/assets/VendorOnboarding-BsmUPytx-v4y044-pr150-review-r5.js"];
let checking=false,queued=false,done=false;
const relevant=()=>/^\/(list-your-shop|partner|vendor|seller|categories)(\/|$)/.test(location.pathname);
const stale=()=>{const body=document.body?.textContent||"";return body.includes("Subcategory (optional; inferred when clear)")||body.includes("Store category unavailable")};
async function refresh(){
 if(done||checking||!relevant())return;
 checking=true;
 try{
   if(sessionStorage.getItem(key)==="done"){done=true;return;}
   const results=await Promise.all(sources.map(async path=>{
     const r=await fetch(path,{cache:"reload",credentials:"same-origin"});
     if(!r.ok)throw new Error("asset not refreshed");
     return r.text();
   }));
   if(!results[0].includes("Health & Pharmacy")||!results[1].includes("v4y-seller-subcats-20261020")){
      throw new Error("new category files not available");
   }
   sessionStorage.setItem(key,"done");done=true;
   location.reload();
 }catch(err){console.warn("Category update needs one hard refresh",err);}
 finally{checking=false;}
}
function tick(){
 if(queued||done||!relevant())return;
 queued=true;
 setTimeout(()=>{queued=false;void refresh()},250);
}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",tick,{once:true});
else tick();
new MutationObserver(tick).observe(document.documentElement,{childList:true,subtree:true});
addEventListener("popstate",tick);
})();
