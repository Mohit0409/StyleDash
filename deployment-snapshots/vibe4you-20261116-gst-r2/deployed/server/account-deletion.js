"use strict";
(function(){
  var statusLine=document.getElementById("status");
  var signedOut=document.getElementById("signed-out");
  var form=document.getElementById("delete-form");
  var label=document.getElementById("account-label");
  var recentNote=document.getElementById("recent-note");
  var passwordField=document.getElementById("password-field");
  var password=document.getElementById("current-password");
  var confirmation=document.getElementById("confirmation");
  var button=document.getElementById("delete-button");
  var deletedBanner=document.getElementById("deleted");
  var csrf="";
  var needsPassword=false;
  var busy=false;

  function say(text,kind){
    statusLine.textContent=text;
    statusLine.className=kind||"";
  }
  function refreshButton(){
    var ready=confirmation.value.trim()==="DELETE"&&(!needsPassword||password.value.length>0);
    button.disabled=busy||!ready;
  }
  function showSignedOut(){
    form.hidden=true;
    signedOut.hidden=false;
    say("You are not signed in.");
  }

  if(new URLSearchParams(location.search).get("deleted")==="1"){
    deletedBanner.hidden=false;
    history.replaceState(history.state,"",location.pathname);
  }

  fetch("/api/auth/me",{credentials:"same-origin",cache:"no-store"}).then(function(response){
    if(response.status===401){showSignedOut();return null;}
    if(!response.ok){throw new Error("unavailable");}
    return response.json();
  }).then(function(data){
    if(!data){return;}
    var user=data.user||{};
    csrf=typeof data.csrfToken==="string"?data.csrfToken:"";
    needsPassword=user.hasPassword===true;
    label.textContent=user.email||user.phone||user.name||"your account";
    passwordField.hidden=!needsPassword;
    password.required=needsPassword;
    recentNote.hidden=needsPassword;
    form.hidden=false;
    say("");
    refreshButton();
  }).catch(function(){
    say("We could not check your sign-in right now. Please reload the page.","error");
  });

  confirmation.addEventListener("input",refreshButton);
  password.addEventListener("input",refreshButton);
  form.addEventListener("submit",async function(event){
    event.preventDefault();
    if(button.disabled){return;}
    busy=true;
    refreshButton();
    say("Deleting your account…");
    var body={confirmation:confirmation.value.trim()};
    if(needsPassword){body.currentPassword=password.value;}
    try{
      var response=await fetch("/api/auth/delete-account",{
        method:"POST",credentials:"same-origin",cache:"no-store",
        headers:{"Content-Type":"application/json","X-CSRF-Token":csrf},
        body:JSON.stringify(body)
      });
      password.value="";
      if(response.ok){
        location.replace("/account-deletion?deleted=1");
        return;
      }
      var payload={};
      try{payload=await response.json();}catch(error){}
      if(response.status===401&&payload.code!=="invalid_credentials"){showSignedOut();return;}
      say(typeof payload.error==="string"&&payload.error?payload.error:"Your account could not be deleted. Please try again.","error");
    }catch(error){
      say("The Vibe4You server is unavailable. Please try again.","error");
    }
    busy=false;
    refreshButton();
  });
})();
