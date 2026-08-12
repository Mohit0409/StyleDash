# StyleDash - Your look, delivered fast.

StyleDash is a production-quality, hyperlocal clothing quick-commerce web application built for 60-minute fashion delivery in Neemuch, MP.

## Features

- **Hyperlocal 60-Min Delivery**: Pincode serviceability verification for Neemuch (`458441`).
- **Complete Fashion Catalogue**: Over 125 clothing, footwear, and accessory products across Men, Women, Kids, and Accessories.
- **Variant-Aware Cart**: Tracks size, colour, SKU, and stock per line item (`productId:variantId`).
- **Product Detail & Size Guide**: Interactive image gallery, colour swatches, size selector, and department measurement charts.
- **Filters & URL Sync**: Filter by department, brand, size, price, and sorting with shareable URL parameters.
- **Order Tracking & Admin Portal**: Live order status timeline (`placed`, `confirmed`, `packed`, `out_for_delivery`, `delivered`) and admin dashboard.
- **Monetization & Referrals**: Vendor commission tracking, sponsored placements, and referral rewards (Give ₹100, Get ₹100).
- **Firebase & Local Demo Mode**: Works out of the box in Local/Demo mode without Firebase credentials.

## Local Setup

```bash
# Install dependencies
npm install

# Start local dev server
npm run dev

# Run TypeScript type check
npm run typecheck

# Run unit tests
npm run test
```

## Environment Configuration

See `.env.example` for environment variable options.

## License
MIT
