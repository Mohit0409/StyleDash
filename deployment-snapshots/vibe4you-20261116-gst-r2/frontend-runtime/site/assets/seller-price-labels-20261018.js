(function () {
  'use strict';

  // Display-only clarification for the shop owner's product price fields.
  // Vibe4You pricing, validation, inventory, and form values remain unchanged.
  var labels = {
    'Price (INR)': 'Price (Selling Price) (INR)',
    'Original price (INR)': 'Original price (MRP) (INR)'
  };

  function updateLabels() {
    if (window.location.pathname !== '/partner' && !window.location.pathname.startsWith('/partner/')) return;
    var root = document.getElementById('root');
    if (!root) return;
    var candidates = root.querySelectorAll('form label');
    for (var i = 0; i < candidates.length; i++) {
      var label = candidates[i];
      if (!label.querySelector('input[type="number"]')) continue;
      for (var node = label.firstChild; node; node = node.nextSibling) {
        if (node.nodeType !== 3) continue;
        var current = node.textContent.trim();
        if (!Object.prototype.hasOwnProperty.call(labels, current)) continue;
        node.textContent = labels[current];
        break;
      }
    }
  }

  function start() {
    var root = document.getElementById('root');
    if (!root) return;
    // Covers page loads and client-side navigation to the shop owner portal.
    var observer = new MutationObserver(updateLabels);
    observer.observe(root, { childList: true, subtree: true });
    updateLabels();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, { once: true });
  } else {
    start();
  }
}());
