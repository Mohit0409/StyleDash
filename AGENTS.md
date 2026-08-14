# StyleDash Agent Operating Rules

This file defines mandatory repository-wide instructions for every Codex
agent working on StyleDash.

These instructions apply to planning, implementation, testing, security
review, deployment, documentation, and release work.

If a task-specific instruction conflicts with this file, follow the safer
instruction and explicitly report the conflict.

---

# 1. Project

StyleDash is a production hyperlocal fashion-commerce application serving
Neemuch, Madhya Pradesh.

Production architecture:

- React 18
- Vite
- TypeScript
- Tailwind CSS
- Python backend
- SQLite
- Android / Termux production host
- public application server: `127.0.0.1:8080`
- private administration server: `127.0.0.1:8081`
- ngrok exposes only public port `8080`
- Razorpay Live payments
- server-side customer authentication
- Argon2id password hashing
- server-side sessions
- CSRF protection
- rate limiting
- private administrator password + TOTP
- SQLite WAL
- online backups
- server-authoritative orders, prices, inventory, and payments

The production branch is `feature/styledash-fashion-commerce` unless the
repository owner explicitly changes it.

Do not reintroduce Firebase as an authoritative system.

Do not treat browser localStorage as authoritative for:

- users
- authentication
- orders
- payments
- inventory
- addresses
- customer account data
- vendor applications
- wallet balances

Local browser storage may be used only for non-authoritative UI convenience
such as temporary cart state or theme settings when appropriate.

---

# 2. Production Safety

StyleDash processes real customer data and real money.

Razorpay is currently configured for Live Mode in production.

Never:

- switch payment mode without explicit user approval
- generate a real payment automatically
- refund a payment automatically unless explicitly requested and reviewed
- modify or delete genuine financial history
- restore an old database over completed financial transactions
- expose payment secrets
- expose customer information
- expose administrator credentials
- expose TOTP secrets
- expose SMTP credentials
- expose SSH private keys
- print, paste, or commit secrets

Any real payment, refund, Live configuration change, database destructive
operation, or production release requires an explicit human gate.

---

# 3. Known-Good Production Baseline

Preserve the existing verified architecture.

Do not weaken:

- Razorpay order creation
- Razorpay server-side payment verification
- Razorpay webhook HMAC verification
- `payment.captured`
- `order.paid`
- `payment.failed`
- `refund.failed`
- `payment.dispute.created`
- exactly-once inventory finalization
- payment idempotency
- webhook idempotency
- payment amount verification
- payment currency verification
- payment order ownership
- customer order ownership and IDOR prevention
- captured-payment requirement
- server-authoritative checkout totals
- customer IDOR protection
- Argon2id authentication
- customer session security
- CSRF protection
- login rate limiting
- password-change session revocation
- private admin architecture
- administrator TOTP
- administrator recovery-code controls
- administrator CSRF
- administrator audit logging
- SQLite WAL
- backup integrity checks

If a change touches any of these systems, it automatically requires Security
Agent review.

---

# 4. Network Boundary

Production public application:

`127.0.0.1:8080`

Private administrator application:

`127.0.0.1:8081`

The administrator service MUST remain loopback-only.

Never bind administrator service to:

- `0.0.0.0`
- LAN interface
- public interface
- ngrok
- Cloudflare public ingress

Public access must continue to return:

`/admin` -> 404

`/api/admin/*` -> 404

ngrok must expose only:

`127.0.0.1:8080`

Never expose SSH publicly as part of an application deployment.

---

# 5. Secrets

Secrets belong only in approved private runtime storage, currently including:

`~/.config/styledash/secrets.env`

Runtime secret files should have restrictive permissions such as `600`.

Never commit:

- `.env` containing credentials
- Razorpay Key Secret
- Razorpay webhook secret
- SMTP password
- TOTP encryption key
- TOTP secret
- administrator recovery codes
- SSH private keys
- session tokens
- password reset tokens

Browser-visible `VITE_*` values must NEVER contain secrets.

A Razorpay Key ID may be browser-visible when required by Razorpay Checkout.

A Razorpay Key Secret must NEVER be browser-visible.

Before every release run a secret scan.

If a real secret is discovered:

STOP.

Report the affected file only.

Do not print the secret.

---

# 6. Database

SQLite contains authoritative production information.

Never casually edit or replace the live database.

Before risky migrations or production changes:

1. run `PRAGMA integrity_check;`
2. create an online SQLite backup
3. validate backup integrity
4. preserve existing financial history

Do not blindly copy an active WAL database if existing online backup tooling is
available.

Never commit:

- `*.db`
- `*.db-wal`
- `*.db-shm`
- production backups
- customer records
- order runtime data
- payment runtime data

Database migrations must be:

- forward-safe
- repeatable/idempotent where applicable
- tested against representative data
- reviewed for rollback consequences

---

# 7. Payment Rules

The server is the final authority.

Never trust browser-provided:

- amount
- subtotal
- tax
- discount
- wallet value
- delivery fee
- inventory
- payment status

A browser callback alone must not fulfill an order.

Online fulfillment requires verified Razorpay state such as:

`captured`

or valid `order.paid` processing through the existing finalization path.

`authorized` does NOT mean fulfilled.

Inventory must decrement exactly once.

Expected pattern:

inventory before = N

first valid payment finalization:
N -> N - quantity

browser retry:
unchanged

`payment.captured` duplicate:
unchanged

`order.paid` duplicate:
unchanged

server restart + duplicate:
unchanged

Any possible double decrement is a release blocker.

---

# 8. Customer Authorization

Every customer-specific server operation must derive customer identity from the
authenticated server session.

Never trust a browser-supplied user ID for authorization.

Customers must not be able to read or mutate:

- another customer's profile
- another customer's address
- another customer's orders
- another customer's payment references
- another customer's vendor application
- administrator resources

IDOR tests are mandatory whenever customer-resource APIs change.

---

# 9. Administrator Security

Public customer authentication and administrator authentication are separate
security domains.

Administrator authentication requires the existing:

- administrator identity
- Argon2id password
- TOTP or approved recovery mechanism
- separate administrator session
- administrator CSRF
- loopback network boundary

Do not create a public administrator login.

Do not create an administrator role through customer registration.

Administrator mutations must remain auditable.

---

# 10. Password Recovery

Password-reset functionality must use secure one-time tokens.

Requirements:

- cryptographically secure random token
- server stores only token hash
- short expiration
- single use
- generic email-request response
- no email-account enumeration
- rate limiting
- new password hashed with existing Argon2id mechanism
- successful reset revokes existing customer sessions

Never:

- return reset token in public API JSON
- log reset token
- store plaintext reset token
- put SMTP credentials in frontend code

---

# 11. Inventory

Server inventory is authoritative.

Frontend inventory is only a display layer.

Any public inventory API must expose only safe availability information.

Do not expose:

- supplier cost
- private merchant data
- customer information
- payment information
- administrator metadata

Before checkout, the server must still revalidate inventory even if the
frontend recently refreshed stock.

Never rely solely on frontend stock.

---

# 12. Serviceability

Checkout service-area validation and public pincode checking must use the same
authoritative backend configuration.

Do not implement broad approximations such as:

`pincode.startsWith("458")`

if the backend supports an exact pincode list.

A public serviceability checker must never tell a customer an address is
supported if secure checkout will reject it.

---

# 13. Temporary Test Product

A temporary low-value payment-validation product may exist.

Requirements:

- controlled by server-side feature flag
- hidden from normal catalogue
- hidden from search
- hidden from recommendations
- hidden from categories
- accessible only through intended controlled flow
- purchase authorization enforced server-side
- price calculated server-side
- clearly marked test/no-fulfillment in administration
- historical paid orders remain after feature is disabled

Never allow arbitrary customers to purchase an owner-only payment test item.

Never automatically perform the Live payment.

---

# 14. Legal and Customer-Facing Content

Do not invent:

- business identity
- address
- phone number
- support email
- refund policy
- return policy
- jurisdiction
- privacy retention period
- support hours

If required legal/business information is missing:

STOP and request it.

Customer-facing policies must be mutually consistent.

For example:

Footer exchange claim
=
Returns page
=
Product Detail claim
=
Terms

Do not leave temporary phrases such as:

- "before Live Mode"
- "Legal review required"
- "Support contact pending"
- "Business details required"
- "Policy decision required"

in a production release.

---

# 15. Referral and Wallet Features

Do not advertise monetary referral rewards unless the backend implements the
full authoritative earning/redemption lifecycle.

If referrals are disabled:

- remove public referral marketing
- disable or remove public route
- prevent unearned wallet usage
- server wallet value remains authoritative

Never trust wallet value supplied by browser.

---

# 16. Source of Truth

Do not assume old documentation is correct.

Determine current behavior from:

1. current production code
2. automated tests
3. current configuration templates
4. deployment scripts
5. verified release reports
6. documentation

If README disagrees with the current architecture, update README rather than
reintroducing obsolete architecture.

In particular, do not reintroduce old Firebase/demo assumptions merely because
they appear in stale documentation.

---

# 17. Roles

Four primary agent roles are used:

## Manager Agent

Owns:

- task decomposition
- requirements
- acceptance criteria
- dependency ordering
- human approval gates
- release decision
- handoff coordination

Manager should avoid large implementation changes.

Manager must not certify work based solely on Developer claims.

---

## Developer Agent

Owns:

- implementation
- migrations
- unit/integration tests for changed code
- documentation updates
- code cleanup
- local verification

Developer does not approve its own release.

Developer must provide a clear handoff to Tester and, when required, Security.

---

## Tester Agent

Owns independent verification.

Tester should prefer not to modify application code.

Tester validates:

- acceptance criteria
- regression
- frontend
- APIs
- auth flows
- negative cases
- mobile/responsive behavior where practical
- browser E2E where available

Tester reports evidence and failures.

Tester does not silently fix defects and then declare PASS.

A defect goes back to Developer.

---

## Security Agent

Owns independent security/release-risk review.

Security Agent focuses on:

- authentication
- authorization
- IDOR
- CSRF
- sessions
- rate limiting
- Razorpay
- webhook integrity
- inventory exactly-once
- secret exposure
- database safety
- administrator isolation
- password reset
- public/private network boundary
- deployment safety

Security Agent should not make large feature changes during review.

Security findings go back to Developer.

---

# 18. Role Separation

Normal flow:

Manager
-> Developer
-> Tester
-> Security when required
-> Manager release decision

A Developer PASS is not sufficient.

A release that touches payment, authentication, authorization, CSRF,
administrator controls, secrets, database, inventory, or production exposure
requires:

Developer: PASS
Tester: PASS
Security: PASS
Manager: RELEASE APPROVED

Only the Manager may write the exact release decision `RELEASE APPROVED`.
Developer, Tester, and Security may report `PASS` for their own scope but must
not self-certify production readiness.

If Tester or Security reports FAIL:

Manager status must remain:

BLOCKED

until fixed and retested.

---

# 19. Handoff Format

Every agent handoff should include:

TASK:
ROLE:
BASE COMMIT:
WORKING/TESTED COMMIT:
FILES CHANGED:
TESTS:
RESULT:
KNOWN RISKS:
MANUAL ACTION REQUIRED:
NEXT ROLE:

Allowed RESULT values:

PASS
FAIL
BLOCKED
MANUAL ACTION REQUIRED

Avoid vague wording such as:

"looks good"
"probably works"
"should be okay"

---

# 20. Git Rules

Before work:

`git status`
`git log -5 --oneline`

Do not work on an unexpected dirty tree without first understanding it.

Do not:

- force push
- rewrite verified release history
- delete release tags
- commit runtime databases
- commit secrets

Prefer one focused commit per coherent task.

Developer branches/worktrees should use names such as:

`agent/dev-<task-id>`

Tester worktrees may use:

`agent/test-<task-id>`

Security worktrees may use:

`agent/security-<task-id>`

Do not have multiple agents editing the same working directory simultaneously.

Use separate Codex worktrees/threads where available.

---

# 21. Testing Baseline

Frontend commands currently include:

`npm run typecheck`

`npm run lint`

`npm run test`

`npm run build`

Run all four before release unless a task genuinely does not involve frontend
code and Manager explicitly scopes them out.

Backend:

Run the complete Python test suite from the repository root with:

`python -m unittest discover -s server/tests -v`

On the Android/Termux production host the equivalent command is:

`python3 -m unittest discover -s server/tests -v`

The complete suite includes:

- authentication
- security
- administrator
- payment
- webhook
- inventory
- database
- recovery tests

Do not reduce existing test coverage or test counts to make a build pass.

Do not:

- comment out failing tests
- weaken assertions
- add arbitrary sleeps to hide race conditions
- disable lint rules globally
- use `@ts-nocheck` to avoid type errors

---

# 22. Browser E2E

A command named `test:e2e` is not proof of true E2E testing.

Currently, `npm run test:e2e` runs
`vitest run src/tests/paymentApi.test.ts`. It is a focused Vitest test, not a
real browser E2E suite. No Playwright, Cypress, or other browser automation
framework is currently configured.

True browser E2E should use an actual browser automation framework such as
Playwright when added to the project.

Priority browser flows:

- homepage
- catalogue
- search
- filters
- product detail
- live inventory display
- cart
- registration
- login
- logout
- password recovery
- profile
- supported/unsupported pincode
- protected checkout
- COD
- cancelled Razorpay Checkout
- customer order history
- IDOR negative test where feasible
- legal/support pages
- referral-disabled behavior
- 404

Do NOT automate a real Razorpay Live payment.

---

# 23. Pre-Release Verification

Before production deployment:

1. frontend typecheck
2. frontend lint
3. frontend tests
4. production build
5. Python tests
6. security regression
7. secret scan
8. `git diff --check`
9. SQLite integrity check where production DB is affected
10. fresh backup where production state can be affected

Any critical failure blocks deployment.

---

# 24. Deployment

Deploy only through the existing supported StyleDash deployment/startup tools.

Do not improvise a new hosting architecture during an unrelated feature task.

Preserve:

public server:
`127.0.0.1:8080`

private admin:
`127.0.0.1:8081`

ngrok:
public 8080 only

After deployment verify:

- `/api/health`
- correct payment mode
- database healthy
- homepage
- relevant changed routes
- `/admin` -> 404 public
- `/api/admin/*` -> 404 public
- private admin remains loopback-only

Do not perform a real transaction unless the user explicitly authorizes the
transaction step.

---

# 25. Rollback

Before risky production changes, identify the rollback point.

Rollback must preserve financial history.

Never resolve an application failure after a captured payment by blindly
restoring an older database.

If Razorpay reports a captured payment but StyleDash is inconsistent:

- stop new affected traffic if necessary
- preserve transaction
- reconcile using payment/order/webhook data
- do not tell customer to simply pay again

---

# 26. Required Final Report

Every completed task must report:

Role
Task
Base commit
Result
Files changed
Tests executed
Test counts
Security impact
Database impact
Payment impact
Deployment performed or not
Manual actions remaining
Known limitations
Recommended next step

For release reviews, use:

READY
BLOCKED
MANUAL ACTION REQUIRED

Do not declare READY when a critical requirement is unverified.

---

# 27. Core Principle

StyleDash handles real people, real orders, and real money.

Correctness, security, recoverability, and truthful customer experience take
priority over speed or task completion.
