/* Progressive installation enhancement; never changes commerce state. */
let installPrompt = null;
let busy = false;
const standalone = () => window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
const ios = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
const panel = document.createElement('aside');
panel.className = 'v4y-install';
panel.setAttribute('aria-label', 'Install Vibe4You');
panel.hidden = true;
panel.innerHTML = '<p>Keep Vibe4You on your home screen for quick access.</p><div><button type="button" data-install>Install app</button><button type="button" data-later>Later</button></div>';
const dialog = document.createElement('dialog');
dialog.className = 'v4y-install-help';
dialog.setAttribute('aria-labelledby', 'v4y-install-title');
dialog.innerHTML = '<h2 id="v4y-install-title">Add Vibe4You to your home screen</h2><p></p><button type="button">Got it</button>';
dialog.querySelector('p').textContent = ios
  ? 'Open this website in Safari. Tap Share, choose Add to Home Screen, enable Open as Web App when available, then tap Add.'
  : 'Open your browser menu and choose Install app or Add to Home screen, when available.';
document.body.append(panel, dialog);
let dismissed = false;
function update() {
  const preferencesOpen = document.querySelector('[aria-label="Analytics preferences"]') !== null;
  panel.hidden = preferencesOpen || standalone() || dismissed || (!ios && !installPrompt);
}
function help() { if (!dialog.open) dialog.showModal(); }
dialog.querySelector('button').addEventListener('click', () => dialog.close());
panel.querySelector('[data-later]').addEventListener('click', () => { dismissed = true; update(); });
panel.querySelector('[data-install]').addEventListener('click', async () => {
  if (busy) return;
  if (!installPrompt) { help(); return; }
  const prompt = installPrompt;
  installPrompt = null;
  busy = true;
  const button = panel.querySelector('[data-install]');
  button.disabled = true;
  try { await prompt.prompt(); await prompt.userChoice; } catch { help(); }
  finally { busy = false; button.disabled = false; update(); }
});
window.addEventListener('beforeinstallprompt', (event) => { event.preventDefault(); installPrompt = event; update(); });
window.addEventListener('appinstalled', () => { installPrompt = null; dismissed = true; update(); });
window.matchMedia('(display-mode: standalone)').addEventListener('change', update);
new MutationObserver(update).observe(document.body, { childList: true, subtree: true });
update();
if ('serviceWorker' in navigator && window.isSecureContext) {
  const register = () => { void navigator.serviceWorker.register('/sw.js', { scope: '/', updateViaCache: 'none' }).catch(() => {}); };
  if (document.readyState === 'complete') register();
  else window.addEventListener('load', register, { once: true });
}
