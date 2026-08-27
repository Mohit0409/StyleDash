# Vibe4You - Your City. Your Shops. Your Style.

Vibe4You is a production-quality, hyperlocal clothing quick-commerce web application built for 60-minute fashion delivery in Neemuch, MP.

## Features

- **Hyperlocal 60-Min Delivery**: Pincode serviceability verification for Neemuch (`458441`).
- **Authoritative Serviceability API**: `/api/serviceability?pincode=<six digits>` checks delivery availability from the same backend configuration used by checkout.
- **Controlled Payment Validation**: An optional server-gated ₹10 Razorpay validation item is hidden from the catalogue and restricted to privately configured, mailbox-verified authenticated accounts; it never enters fulfillment or fashion inventory.
- **Complete Fashion Catalogue**: Over 125 clothing, footwear, and accessory products across Men, Women, Kids, and Accessories.
- **Variant-Aware Cart**: Tracks size, colour, SKU, and stock per line item (`productId:variantId`).
- **Product Detail & Size Guide**: Interactive image gallery, colour swatches, size selector, and department measurement charts.
- **Filters & URL Sync**: Filter by department, brand, size, price, and sorting with shareable URL parameters.
- **Order Tracking & Admin Portal**: Live order status timeline (`placed`, `confirmed`, `packed`, `out_for_delivery`, `delivered`) and admin dashboard.
- **Marketplace Monetization**: Vendor commission tracking and sponsored placements. Referral and wallet rewards are not currently offered.
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
