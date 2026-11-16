/* Vibe4You review/photo enhancement, independent of the current SPA build. */
(() => {
  'use strict';
  const nativeFetch = window.fetch.bind(window);
  const state = {
    product: { reviews: [], eligibility: null, photo: null, removePhoto: false, working: false },
    store: { reviews: [], eligibility: null, photo: null, removePhoto: false, working: false },
    path: window.location.pathname,
  };
  let scheduled = false;
  const endpointKind = path => path.startsWith('/api/store-reviews') ? 'store' :
    path.startsWith('/api/reviews') ? 'product' : null;
  const targetSection = kind => document.querySelector(
    kind === 'product' ? 'section[aria-labelledby="customer-reviews-heading"]' :
      'section[aria-labelledby="store-reviews-heading"]');
  const safePhoto = url => typeof url === 'string' &&
    /^\/api\/review-photo\/(?:rev_|store_rev_)[a-z0-9_-]{4,64}$/.test(url);

  window.fetch = async (input, init) => {
    const inputUrl = typeof input === 'string' ? input : input && input.url;
    const address = new URL(inputUrl || location.href, location.href);
    const path = address.pathname;
    const kind = endpointKind(path);
    const method = String((init && init.method) || (input && input.method) || 'GET').toUpperCase();
    const exactList = path === '/api/reviews' || path === '/api/store-reviews';
    const isSubmit = kind && method === 'POST' &&
      (exactList || /^\/api\/(?:reviews|store-reviews)\/[^/]+\/edit$/.test(path));
    let changed = init;
    if (isSubmit && state[kind].working) {
      throw new Error('Please finish preparing your review photo before submitting.');
    }
    if (isSubmit && (state[kind].photo || state[kind].removePhoto)) {
      try {
        const request = JSON.parse(String(init && init.body || '{}'));
        if (state[kind].photo) request.photoDataUrl = state[kind].photo;
        else if (state[kind].removePhoto) request.removePhoto = true;
        changed = Object.assign({}, init, { body: JSON.stringify(request) });
      } catch (_) { /* No changes to unexpected request bodies. */ }
    }
    const response = await nativeFetch(input, changed);
    if (kind && method === 'GET' &&
        (exactList || path.endsWith('/eligibility')) && response.ok) {
      response.clone().json().then(payload => {
        if (exactList && Array.isArray(payload.reviews)) state[kind].reviews = payload.reviews;
        else if (path.endsWith('/eligibility')) state[kind].eligibility = payload;
        schedule();
      }).catch(() => {});
    }
    if (isSubmit && response.ok) {
      state[kind].photo = null;
      state[kind].removePhoto = false;
      schedule();
    }
    return response;
  };

  // Decode using browser-native paths in order of reliability. Some Android
  // photo pickers reject HTMLImageElement.decode() even for valid JPEG files.
  const loadImageElement = src => new Promise((resolve, reject) => {
    const image = new Image();
    let finished = false;
    const done = error => {
      if (finished) return;
      finished = true;
      clearTimeout(timeout);
      image.onload = null;
      image.onerror = null;
      if (error) reject(error);
      else resolve(image);
    };
    const timeout = setTimeout(() => done(new Error('Image loading timed out.')), 15000);
    image.onload = () => done(image.naturalWidth && image.naturalHeight ?
      null : new Error('Image dimensions were not available.'));
    image.onerror = () => done(new Error('The browser could not open this image.'));
    image.src = src;
  });

  const readAsDataURL = file => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(new Error('The selected photo could not be read.'));
    reader.readAsDataURL(file);
  });

  const parsePhoto = async file => {
    const type = String(file && file.type || '').toLowerCase();
    const suffix = String(file && file.name || '').toLowerCase();
    const supportedType = /^(image\/(?:jpeg|png|webp|avif|heic|heif))$/.test(type);
    const supportedSuffix = /\.(?:jpe?g|png|webp|avif|heic|heif)$/.test(suffix);
    if (!file || file.size === 0 || file.size > 10 * 1024 * 1024 ||
        !(supportedType || (!type && supportedSuffix)))
      throw new Error('Choose a photo (JPG, PNG, WebP, AVIF or HEIC) up to 10 MB.');
    const heic = /(?:heic|heif)/.test(type) || /\.(?:heic|heif)$/.test(suffix);
    let bitmap = null;
    let image = null;
    let blobUrl = null;
    try {
      // A bitmap avoids HTMLImageElement.decode(), which can fail on mobile.
      if (typeof createImageBitmap === 'function') {
        try { bitmap = await createImageBitmap(file); } catch (_) { /* Try other decoders. */ }
      }
      if (!bitmap) {
        blobUrl = URL.createObjectURL(file);
        try {
          image = await loadImageElement(blobUrl);
        } catch (_) {
          // Some Android photo providers work via a data URL but not a blob URL.
          try { image = await loadImageElement(await readAsDataURL(file)); }
          catch (_) {
            throw new Error(heic ?
              'This browser cannot open HEIC photos. Please select a JPG photo or take a new photo.' :
              'Unable to open this photo. Please try another JPG or PNG, or take a new photo.');
          }
        }
      }
      const source = bitmap || image;
      const width = bitmap ? bitmap.width : image.naturalWidth;
      const height = bitmap ? bitmap.height : image.naturalHeight;
      if (!width || !height || width * height > 45000000)
        throw new Error('This photo is too large to process. Please use a smaller photo.');
      for (const edge of [1000, 750, 600, 420]) {
        const scale = Math.min(1, edge / Math.max(width, height));
        const canvas = document.createElement('canvas');
        canvas.width = Math.max(1, Math.round(width * scale));
        canvas.height = Math.max(1, Math.round(height * scale));
        const ctx = canvas.getContext('2d', {alpha:false});
        if (!ctx) throw new Error('Image processing is unavailable.');
        ctx.drawImage(source, 0, 0, canvas.width, canvas.height);
        for (const quality of [.8, .65, .5, .35, .25]) {
          const encoded = canvas.toDataURL('image/webp', quality);
          if (encoded.startsWith('data:image/webp;base64,') && encoded.length < 230000)
            return encoded;
        }
      }
      throw new Error('This photo is too detailed to upload. Please try a smaller photo.');
    } finally {
      if (bitmap && typeof bitmap.close === 'function') bitmap.close();
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    }
  };

  const decorateForm = (kind, section) => {
    const form = section.querySelector('form');
    if (!form) return;
    const saved = state[kind];
    const eligible = saved.eligibility;
    const submit = form.querySelector('button[type="submit"]');
    const heading = form.querySelector('h3, h4');
    if (heading) {
      const value = eligible && eligible.existingReview ? 'Edit your review' : 'Write a review';
      if (heading.textContent !== value) heading.textContent = value;
    }
    if (submit && !saved.working) {
      const label = 'Submit';
      if (submit.textContent !== label) submit.textContent = label;
    }
    form.querySelectorAll('p').forEach(p => {
      if (/Verified delivered purchase/.test(p.textContent || '')) {
        const label = eligible && eligible.existingReview && eligible.existingReview.status === 'pending' ?
          'Awaiting admin approval. Editing will resubmit your review.' :
          'No purchase necessary. Visible only after admin approval.';
        if (p.textContent !== label) p.textContent = label;
      }
    });
    let wrapper = form.querySelector('.v4y-review-photo');
    if (!wrapper) {
      wrapper = document.createElement('div');
      wrapper.className = 'v4y-review-photo';
      wrapper.style.cssText = 'display:flex;flex-direction:column;gap:7px;margin:12px 0;font-size:12px;';
      const label = document.createElement('label');
      label.textContent = 'Add a review photo (optional)';
      label.style.fontWeight = '700';
      const fileInput = document.createElement('input');
      fileInput.type = 'file';
      fileInput.accept = 'image/*';
      fileInput.setAttribute('aria-label', 'Add a review photo');
      fileInput.style.cssText = 'display:block;margin-top:6px;max-width:100%;';
      label.appendChild(fileInput);
      const feedback = document.createElement('span');
      feedback.className = 'v4y-photo-feedback';
      const preview = document.createElement('img');
      preview.className = 'v4y-photo-preview';
      preview.alt = 'Your review photo preview';
      preview.style.cssText = 'width:130px;height:130px;object-fit:contain;border:1px solid #ddd;border-radius:12px;';
      preview.hidden = true;
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'v4y-photo-remove';
      remove.style.cssText = 'align-self:flex-start;font-size:12px;text-decoration:underline';
      remove.textContent = 'Remove attached photo';
      remove.hidden = true;
      fileInput.addEventListener('change', async () => {
        const file = fileInput.files && fileInput.files[0];
        if (!file) return;
        saved.working = true;
        feedback.textContent = 'Preparing photo...';
        try {
          saved.photo = await parsePhoto(file);
          saved.removePhoto = false;
          feedback.textContent = 'Photo ready. It will stay private until approval.';
          preview.src = saved.photo;
          preview.hidden = false;
          remove.hidden = false;
        } catch (error) {
          saved.photo = null;
          fileInput.value = '';
          preview.removeAttribute('src');
          preview.hidden = true;
          remove.hidden = true;
          feedback.textContent = error.message || 'Could not process photo.';
        } finally {
          saved.working = false;
        }
      });
      remove.addEventListener('click', () => {
        saved.photo = null; saved.removePhoto = true;
        fileInput.value = ''; preview.removeAttribute('src'); preview.hidden = true;
        remove.hidden = true; feedback.textContent = 'Photo will be removed when you resubmit.';
      });
      wrapper.append(label, feedback, preview, remove);
      if (submit) submit.before(wrapper);
      else form.appendChild(wrapper);
    }
    const preview = wrapper.querySelector('.v4y-photo-preview');
    const remove = wrapper.querySelector('.v4y-photo-remove');
    const feedback = wrapper.querySelector('.v4y-photo-feedback');
    if (saved.photo && preview && preview.getAttribute('src') !== saved.photo) {
      preview.src = saved.photo;
      preview.hidden = false;
      remove.hidden = false;
      feedback.textContent = 'Photo ready. It will stay private until approval.';
    }
    if (eligible && eligible.existingReview && eligible.existingReview.hasPhoto &&
        !saved.photo && !saved.removePhoto && feedback && !feedback.textContent) {
      feedback.textContent = 'Your existing review has a photo.';
      remove.hidden = false;
    }
  };

  const decorateArticles = (kind, section) => {
    const articles = section.querySelectorAll('article');
    const reviews = state[kind].reviews;
    if (!reviews || !reviews.length) return;
    articles.forEach((article, index) => {
      const review = reviews[index];
      if (!review || !article.textContent.includes(review.comment)) return;
      const current = article.querySelector('img.v4y-review-public-photo');
      if (safePhoto(review.photoUrl)) {
        if (!current || current.getAttribute('src') !== review.photoUrl) {
          if (current) current.remove();
          const image = document.createElement('img');
          image.className = 'v4y-review-public-photo';
          image.loading = 'lazy';
          image.alt = 'Customer review photo';
          image.src = review.photoUrl;
          image.style.cssText = 'width:160px;max-width:100%;height:160px;object-fit:contain;border-radius:12px;margin-top:12px;';
          article.appendChild(image);
        }
      } else if (current) current.remove();
      if (kind === 'product' && !review.verifiedPurchase) {
        article.querySelectorAll('p').forEach(p => {
          if ((p.textContent || '').trim() === 'Verified Purchase') p.textContent = 'Customer Review';
        });
      }
    });
  };

  const adjustCopy = (kind, section) => {
    section.querySelectorAll('p').forEach(p => {
      if (/^Based on \d+ verified reviews?$/.test((p.textContent || '').trim()))
        p.textContent = p.textContent.replace('verified', 'approved');
      else if (/from \d+ verified customer reviews?$/.test(p.textContent || ''))
        p.textContent = p.textContent.replace('verified', 'approved');
      else if (/to review a delivered (purchase|local-store purchase)/.test(p.textContent || ''))
        p.textContent = p.textContent.replace('to review a delivered local-store purchase', 'to review this store')
          .replace('to review a delivered purchase', 'to share a review');
      else if (/Be the first verified customer to review/.test(p.textContent || ''))
        p.textContent = p.textContent.replace('verified customer', 'customer');
    });
  };

  function refresh() {
    if (location.pathname !== state.path) {
      state.path = location.pathname;
      for (const kind of ['product','store']) {
        state[kind].photo = null;
        state[kind].removePhoto = false;
        state[kind].reviews = [];
        state[kind].eligibility = null;
      }
    }
    for (const kind of ['product','store']) {
      const section = targetSection(kind);
      if (!section) continue;
      decorateForm(kind, section);
      decorateArticles(kind, section);
      adjustCopy(kind, section);
    }
  }
  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => { scheduled = false; refresh(); });
  }
  document.addEventListener('DOMContentLoaded', () => {
    new MutationObserver(schedule).observe(document.getElementById('root') || document.body,
      {childList:true,subtree:true});
    schedule();
  });
})();

