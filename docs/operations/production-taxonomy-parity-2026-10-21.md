# Vibe4You production taxonomy parity — 21 Oct 2026

This integration branch updates editable source code to use the **19-category** vocabulary already deployed on the Ubuntu production server. Changes are limited to the canonical Python category rules, store category options, admin product selectors, React category options and tests.

The **Health & Nutrition** category has production subcategory suggestions including protein, creatine, vitamins and sports nutrition. It coexists with Health & Pharmacy.

The high-top boots classification rule and automatic search tag aliases in the Python normalizer also match the running production module.

## Verified reference

Production integrity manifest SHA-256:
0548d8067964ea4fcd62ba364f5501fb781b3b78806e7924c83d1e9b10197db2

The entire, byte-for-byte, code-only production snapshot (1,122 tracked source/assets) is preserved in **private** repository Mohit0409/Vibe4You-Production-Mirror, release 2026-10-21. Do not copy those compiled runtime bundles over editable React source indiscriminately.

154 category/subcategory database corrections were made on production, tested and documented in the private mirror's audit CSV. This source branch does not mutate or include production SQLite, orders, payments or customer records.

**Scope warning:** The public StyleDash main branch also predates additional independently deployed production hotfixes (SEO, GST, UI, payments and other code). Those require separate, reviewed source-parity reconciliation before main can be declared identical to production. Do not deploy this source branch to production without completing that review and the full regression gates.