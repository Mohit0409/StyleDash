# StyleDash Multi-Agent Handoff

Copy one handoff block for every role transition. Do not replace evidence with
vague statements such as "looks good" or "should work."

Allowed `RESULT` values are exactly:

- `PASS`
- `FAIL`
- `BLOCKED`
- `MANUAL ACTION REQUIRED`

## Required role handoff

```text
TASK:
ROLE: Manager | Developer | Tester | Security
BASE COMMIT:
WORKING/TESTED COMMIT:
FILES CHANGED:
TESTS:
RESULT: PASS | FAIL | BLOCKED | MANUAL ACTION REQUIRED
KNOWN RISKS:
MANUAL ACTION REQUIRED:
NEXT ROLE:
```

`WORKING/TESTED COMMIT` means the Developer's working commit for a Developer
handoff and the exact reviewed commit for Tester or Security. Manager records
the candidate commit it evaluated.

## Optional supporting evidence

Add acceptance-criterion results, reproduction steps, test counts, security
findings, database/payment impact, and unverified areas after the required
fields. Every failure should name the affected commit and give reproducible
evidence.

## Workflow and release decision

The normal sequence is:

```text
Manager -> Developer -> Tester -> Security when required -> Manager
```

Tester and Security validate independently, preferably in separate Codex
threads/worktrees at the exact Developer commit. A failed review returns to
Developer and must be retested.

Only Manager may append this decision after all required handoffs:

```text
RELEASE DECISION: RELEASE APPROVED | BLOCKED | MANUAL ACTION REQUIRED
REASON:
NEXT ACTION:
```

Developer, Tester, and Security must never write `RELEASE APPROVED`.
