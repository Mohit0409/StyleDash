# Compiled V4Y-046 -> V4Y-056 R13 release replay

The exact historical V4Y-056 R13 Python build source and its
public, already-compiled V4Y-046 Category/Social input are archived
under this folder.

Use the offline tool:

    py -3.12 scripts/replay_v4y046_to_r13_offline.py

The R13 builder consumes:
- 53 SHA-256-pinned public V4Y-046 JS chunks and the V4Y-046 homepage;
- the original V4Y-046 release integrity manifest;
- the verified historical R13 backend code candidate (serve.py);
- the unmodified original scripts/build_v4y056_storefront_hardening.py.

It recreates the 53 versioned JS chunks, homepage, backend serve.py,
nonsecret service environment drop-in, and candidate.sha256 checksums.
All 56 code/config output hashes and the exact generated manifest
match the archived R13 release. Its 54 storefront files also match
the canonical R13 input used for R13 -> R3 Search V2 replay.

The historically deployed R13 patch implemented page-scoped review
summary requests, a visible catalogue loading status, and an origin
configuration update. The builder is run with Python isolated flags
inside a throwaway OS-temp directory. No Ubuntu services, orders,
customer data, GST records, billing or production files are touched.

The new offline replay never attempts a deployment or a GitHub merge.
The archived backend is historical code, not an authorized production
replacement. Its 378 KB of code were parsed and screened for high-risk
literal secret formats before inclusion.

**Limitation:** V4Y-046 itself is compiled public output. The original
editable React source and exact production V4Y-046 build provenance
still need to be reconstructed. Separately installed marketing,
review, SEO, PWA and CSS overlays also remain outside this replay.

Together with the other stage replays, the current compiled chain is:

V4Y-046 (54 public code inputs)
 -> V4Y-056 R13 (56 code/config outputs, 54 storefront)
 -> V4Y-055 R3 (56 outputs, 54 storefront)
 -> Search V2 (54 storefront)
 -> Search V2 R2 (54 storefront, exact current Ubuntu public hashes).
