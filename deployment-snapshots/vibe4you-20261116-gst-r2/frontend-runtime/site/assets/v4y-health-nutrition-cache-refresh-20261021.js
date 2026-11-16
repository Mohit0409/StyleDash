/* Health & Nutrition category cache refresh. Cache only, no product or account changes. */
(() => {
"use strict";
const key="v4y-hn-20261021-v1";
const chunks=[
["/assets/index-MMTPd8z_-v4y044-pr150-review-r5.js","Health & Nutrition"],
["/assets/categories-C-uMYXyt-v4y044-pr150-review-r5.js","Health & Nutrition"],
["/assets/VendorOnboarding-BsmUPytx-v4y044-pr150-review-r5.js","Health & Nutrition"],
["/assets/v4y-mobile-ui-fix-20261021.js","Health%20%26%20Nutrition"]
];
async function run(){
try{
if(sessionStorage.getItem(key)==="done")return;
await Promise.all(chunks.map(async ([url,marker])=>{
 const response=await fetch(url,{cache:"reload",credentials:"same-origin"});
 if(!response.ok)throw new Error("asset:"+url);
 const body=await response.text();
 if(!body.includes(marker))throw new Error("category marker:"+url);
}));
sessionStorage.setItem(key,"done");location.reload();
}catch(err){console.warn("Vibe4You nutrition category cache refresh pending.",err);}
}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",run,{once:true});else void run();
})();
