# 🛵 Neemuch Blink

**Everything you need, delivered fast.**

Neemuch's fastest grocery delivery app — fresh groceries, vegetables, fruits, dairy, snacks and daily essentials delivered in 10–20 minutes.

---

## 🚀 Tech Stack

| Layer | Tech |
|---|---|
| Frontend | React 18 + Vite + TypeScript |
| Styling | Tailwind CSS v3 + Framer Motion |
| Icons | Lucide React |
| Routing | React Router v6 |
| Backend | Firebase (Auth + Firestore + Storage + Hosting) |
| PWA | vite-plugin-pwa |

---

## 📁 Project Structure

```
neemuch-blink/
├── public/
│   ├── favicon.svg
│   ├── robots.txt
│   └── sitemap.xml
├── src/
│   ├── components/       # Reusable UI components
│   │   ├── Navbar.tsx
│   │   ├── Footer.tsx
│   │   ├── ProductCard.tsx   # incl. sponsored badge + ad tracking
│   │   ├── CategoryCard.tsx
│   │   ├── Banner.tsx
│   │   ├── CartDrawer.tsx
│   │   ├── FloatingCartButton.tsx
│   │   └── Skeleton.tsx
│   ├── context/          # React Context providers
│   │   ├── AuthContext.tsx
│   │   ├── CartContext.tsx
│   │   ├── WishlistContext.tsx
│   │   ├── ThemeContext.tsx
│   │   ├── ToastContext.tsx
│   │   └── ReferralContext.tsx   # give/get reward wallet
│   ├── data/             # Static mock data
│   │   ├── products.ts   # 90+ products (some sponsored/vendor-tagged)
│   │   ├── categories.ts # 10 categories
│   │   ├── banners.ts    # Banners + coupons
│   │   └── vendors.ts    # Vendor commission partners + ad slots
│   ├── firebase/
│   │   ├── config.ts     # Firebase init incl. Analytics (add your config)
│   │   └── analytics.ts  # Typed e-commerce + monetization event tracking
│   ├── layouts/
│   │   └── MainLayout.tsx
│   ├── pages/
│   │   ├── Home.tsx          # Landing page
│   │   ├── Categories.tsx
│   │   ├── Products.tsx      # Listing + filters
│   │   ├── Checkout.tsx
│   │   ├── OrderSuccess.tsx
│   │   ├── Orders.tsx
│   │   ├── Referrals.tsx     # Refer & earn page
│   │   ├── Profile.tsx
│   │   ├── Wishlist.tsx
│   │   └── admin/
│   │       └── AdminDashboard.tsx
│   ├── types/
│   │   └── index.ts
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css
├── firebase.json
├── firestore.rules
├── firestore.indexes.json
├── tailwind.config.js
├── vite.config.ts
└── package.json
```

---

## ⚙️ Setup

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Firebase

1. Go to [Firebase Console](https://console.firebase.google.com)
2. Create a new project named **neemuch-blink**
3. Enable **Authentication** (Email, Google, Phone)
4. Enable **Firestore Database**
5. Enable **Storage**
6. Copy your config and update `src/firebase/config.ts`:

```ts
const firebaseConfig = {
  apiKey: "your_api_key",
  authDomain: "your_project.firebaseapp.com",
  projectId: "your_project_id",
  storageBucket: "your_project.appspot.com",
  messagingSenderId: "your_sender_id",
  appId: "your_app_id"
}
```

### 3. Run Locally

```bash
npm run dev
```

Open [http://localhost:5173](http://localhost:5173)

---

## 🚢 Deploy to Firebase Hosting

```bash
# Install Firebase CLI (once)
npm install -g firebase-tools

# Login
firebase login

# Initialize (select Hosting, use 'dist' as public dir)
firebase init hosting

# Build the app
npm run build

# Deploy
firebase deploy
```

Your app will be live at `https://your-project-id.web.app`

### Deploy Firestore rules & indexes

```bash
firebase deploy --only firestore:rules
firebase deploy --only firestore:indexes
```

---

## 🔑 Demo Credentials

| Role | Email | Password |
|---|---|---|
| Admin | admin@neemuchblink.in | any |
| User | user@example.com | any |

> Note: Auth is mocked for demo. Replace with real Firebase Auth in production.

---

## 🎨 Theme Colors

| Name | Hex |
|---|---|
| Primary Yellow | `#FFD400` |
| Primary Green | `#00C853` |
| Dark | `#101010` |
| White | `#FFFFFF` |

---

## 📱 Features

- ✅ Dark / Light mode
- ✅ PWA (installable, offline-ready)
- ✅ Responsive mobile-first design
- ✅ Animated hero, banners, cards
- ✅ Cart with coupon codes & live totals
- ✅ Wishlist with localStorage persistence
- ✅ Product filtering (category, price, rating, discount)
- ✅ Order tracking with progress steps
- ✅ Admin dashboard (stats, products, orders, users, **earnings**)
- ✅ Toast notifications
- ✅ Skeleton loaders
- ✅ SEO meta tags + Open Graph + structured data
- ✅ Firestore security rules
- ✅ Firebase Hosting config
- ✅ **Firebase Analytics** (full e-commerce event funnel)
- ✅ **Monetization toolkit** (sponsored products, vendor commissions, ad slots, referral program)

---

## 💰 Monetization & Analytics

This app ships with a working revenue toolkit, not just a storefront. Four
income streams are wired end-to-end — from the UI down to the admin
dashboard that tracks them:

| Revenue Stream | How it works | Where to see it |
|---|---|---|
| **Delivery fees** | ₹30 fee on orders under ₹300, waived above that | `Cart` / `Checkout` totals |
| **Vendor commission** | Each product can carry a `vendorId` + `commissionPercent`. The platform earns a cut of every sale. National brands (Lay's, Coca-Cola) and local Neemuch shops are pre-seeded as vendors. | `src/data/vendors.ts`, Admin → **Earnings** tab |
| **Sponsored placements** | Brands pay to have a product flagged `sponsored: true`. It gets a "Sponsored" badge, priority styling, and fires `ad_impression` / `ad_click` analytics events (impression only counts when ≥50% of the card is actually scrolled into view). | `ProductCard.tsx`, Admin → **Earnings** tab |
| **Referral program** | "Give ₹50, Get ₹50" — every user gets a stable referral code; redeeming a friend's code credits a wallet. Production version should move the reward-crediting logic into a Cloud Function rather than the client. | `/referrals` page, `ReferralContext.tsx` |

### Setting up Firebase Analytics

1. In Firebase Console, open your project → **Project Settings** → **General**
2. Scroll to **Your apps** → make sure Analytics is enabled for the web app
3. Copy the `measurementId` (looks like `G-XXXXXXXXXX`)
4. Add it to your `.env.local`:
   ```
   VITE_FIREBASE_MEASUREMENT_ID=G-XXXXXXXXXX
   ```
5. That's it — `src/firebase/config.ts` automatically initializes Analytics
   only when a `measurementId` is present and the browser supports it
   (`isSupported()` guards against SSR/unsupported environments, so the
   app never crashes if Analytics isn't configured yet).

### Events already wired up (`src/firebase/analytics.ts`)

Standard GA4 e-commerce funnel: `search`, `view_item_list`, `add_to_cart`,
`remove_from_cart`, `add_to_wishlist`, `view_cart`, `begin_checkout`,
`select_promotion` (coupons), `purchase`.

Custom monetization events: `ad_impression`, `ad_click`,
`referral_shared`, `referral_redeemed`, `vendor_onboarded`.

All of these show up automatically in the Firebase Analytics dashboard
under **Events**, and — if you link Google Ads or enable BigQuery
export — feed straight into remarketing audiences and custom revenue
SQL queries.

### Turning this into real money

The data model is ready; what's left is operational:

1. **Vendor commission** — replace the mocked `unitsSoldMock()` function
   in `AdminDashboard.tsx` with a real aggregation query over your
   `orders` Firestore collection, grouped by `vendorId`.
2. **Ad slots** — build a simple form (or use the Firebase Console
   directly) to let brands/local shops purchase a slot; write it to the
   `adSlots` collection; the storefront already reads `sponsored: true`
   products and renders them with tracking.
3. **Referrals** — move reward crediting into a Cloud Function triggered
   on `referrals` document creation, so a malicious client can't grant
   itself unlimited wallet credit.
4. **Payouts** — settle vendor commissions and ad revenue via UPI/bank
   transfer on a monthly cycle; the Earnings tab gives you the numbers
   to reconcile against.

---

## 📞 Business Info

- **Brand:** Neemuch Blink
- **Location:** Neemuch, Madhya Pradesh 458441
- **Delivery:** 10–20 Minutes
- **Phone:** +91 90000 00000
- **Email:** support@neemuchblink.in

---

Made with ❤️ in Neemuch, MP 🇮🇳
