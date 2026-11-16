"use strict";
(function(){
  var message=document.getElementById("message");
  var form=document.getElementById("verify-form");
  var password=document.getElementById("password");
  var button=document.getElementById("verify");
  var token=new URLSearchParams(location.hash.slice(1)).get("token");
  history.replaceState(history.state,"",location.pathname);
  if(!token||!/^[A-Za-z0-9_-]{43}$/.test(token)){
    token=null;
    message.textContent="This verification link is invalid or expired. Register again to request a fresh email.";
    return;
  }
  password.disabled=false;
  button.disabled=false;
  form.addEventListener("submit",async function(event){
    event.preventDefault();
    if(!token){return;}
    if(!password.value){
      message.textContent="Enter the password you chose when registering.";
      password.focus();
      return;
    }
    button.disabled=true;
    password.disabled=true;
    message.textContent="Verifying your email…";
    try {
      var response=await fetch("/api/auth/register/confirm",{
        method:"POST",credentials:"same-origin",cache:"no-store",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({token:token,password:password.value})
      });
      password.value="";
      if(response.ok){
        token=null;
        message.textContent="Email verified. Opening your account…";
        location.assign("/profile");
        return;
      }
      message.textContent=response.status===429
        ?"Too many attempts. Wait a minute, then try again."
        :"The link is invalid or expired, or the password does not match the one you chose when registering. Try again, or register again to receive a new link.";
    }catch(_){
      message.textContent="Could not connect. Check your connection and try again.";
    }
    button.disabled=false;
    password.disabled=false;
    password.focus();
  });
})();
