"use strict";
// V4Y-054: Google Play account deletion and privacy notice additions.
// Adds a "Delete account" entry to My Profile, the Android app, location and
// account deletion sections to the privacy notice, and a footer link. Each
// insertion is idempotent and only touches pages where its anchor exists.
(function(){
  var MARK="data-v4y054";
  var DELETE_URL="/account-deletion";

  function el(tag,className,text){
    var node=document.createElement(tag);
    if(className){node.className=className;}
    if(text){node.textContent=text;}
    node.setAttribute(MARK,"");
    return node;
  }
  function byText(selector,text){
    var nodes=document.querySelectorAll(selector);
    for(var i=0;i<nodes.length;i++){
      if((nodes[i].textContent||"").trim()===text){return nodes[i];}
    }
    return null;
  }
  function section(heading,paragraphs){
    var wrap=el("section","space-y-2");
    wrap.appendChild(el("h2","font-black",heading));
    paragraphs.forEach(function(item){
      var p=el("p","text-sm text-neutral-600");
      if(typeof item==="string"){p.textContent=item;}else{item(p);}
      wrap.appendChild(p);
    });
    return wrap;
  }

  function profile(){
    if(location.pathname!=="/profile"){return;}
    var logout=byText("button","Logout");
    if(!logout||!logout.parentNode||logout.parentNode.querySelector("["+MARK+"]")){return;}
    var link=el("a","w-full flex gap-3 p-4 rounded-2xl border border-red-200 text-red-700 font-bold");
    link.href=DELETE_URL;
    link.textContent="Delete account";
    link.setAttribute("aria-label","Delete account permanently");
    logout.parentNode.insertBefore(link,logout.nextSibling);
  }

  function privacy(){
    if(location.pathname!=="/privacy"){return;}
    var anchorHeading=byText("h2","Access, correction, and deletion requests");
    var anchor=anchorHeading&&anchorHeading.parentNode;
    if(!anchor||!anchor.parentNode||anchor.parentNode.querySelector("["+MARK+"]")){return;}
    var page=anchor.parentNode;
    page.insertBefore(section("Android app",[
      "This notice also applies to the Vibe4You Android app. The app opens the Vibe4You website at vibe4you.in and collects no additional information of its own."
    ]),anchor);
    page.insertBefore(section("Location",[
      "Vibe4You delivers only to selected areas of Neemuch. If you select the option to use your current location, your browser or phone asks for permission and then shares your precise device location with Vibe4You. It is used to check whether we can deliver to you. When an order needs a confirmed delivery location, the location is saved with that order's delivery address so the order can be delivered. Location is never collected in the background, and you can refuse or withdraw the permission in your browser or phone settings at any time."
    ]),anchor);
    page.insertBefore(section("Deleting your account",[function(p){
      p.appendChild(document.createTextNode("You can permanently delete your account yourself from My Profile in the website or Android app. This removes your profile, contact details, saved addresses, cart, wishlist, reviews, and linked sign-in methods, and signs you out everywhere. Order, payment, and invoice records are kept as described under Retention. "));
      var a=el("a","underline font-bold","Step-by-step instructions and details");
      a.href=DELETE_URL;
      p.appendChild(a);
      p.appendChild(document.createTextNode("."));
    }]),anchor);
    var dated=null;
    var notes=page.querySelectorAll("p");
    for(var i=0;i<notes.length;i++){
      if((notes[i].textContent||"").indexOf("Current policy effective date")===0){dated=notes[i];}
    }
    if(dated){
      var updated=el("p","text-xs text-neutral-500","Android app, location and account deletion sections added November 2026.");
      dated.parentNode.insertBefore(updated,dated.nextSibling);
    }
  }

  function footer(){
    var heading=byText("h5","Your Account");
    var list=heading&&heading.nextElementSibling;
    if(!list||list.tagName!=="UL"||list.querySelector("["+MARK+"]")){return;}
    var item=el("li");
    var a=el("a","hover:text-lime-400","Delete Account");
    a.href=DELETE_URL;
    item.appendChild(a);
    list.appendChild(item);
  }

  var queued=false;
  function run(){
    queued=false;
    try{profile();}catch(error){}
    try{privacy();}catch(error){}
    try{footer();}catch(error){}
  }
  function schedule(){
    if(queued){return;}
    queued=true;
    (window.requestAnimationFrame||setTimeout)(run);
  }
  function start(){
    run();
    new MutationObserver(schedule).observe(document.body,{childList:true,subtree:true});
  }
  if(document.readyState==="loading"){document.addEventListener("DOMContentLoaded",start);}else{start();}
})();
