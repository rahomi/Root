# Root

Association management app for **Root**: members, capital ledger, investments, and snapshot-based profit/loss distribution. Full requirements live in [`SRS_Root_App_v2.pdf`](SRS_Root_App_v2.pdf).

## Overview

Root is a financial ledger and investment allocation platform built around **authorized** capital changes and **historical snapshots** so allocations stay correct over time. Member capital submissions are **requests** until staff with the right permissions approve them; balances and snapshots only reflect posted, authorized activity.

## MVP scope (summary)

- **Roles**: Super Admin, Admin, and Member — with **permission-based** capabilities (who may approve submissions, create investments, release funds, distribute, etc.).
- **Member submission requests**: Installments / capital submissions with payment evidence (channel, optional transaction ID, notes, optional image); pending until approved or rejected.
- **Ledger**: Member flow via approved requests; admin-direct entries where policy allows (`SUBMISSION`, `WITHDRAW`, `ADJUSTMENT`).
- **Investments**: Lifecycle with fund release, snapshot at defined points, close, and distribution.
- **Reporting & audit**: Statements, approval queues, exports, audit logs.

**Out of MVP**: Automated confirmation with banks or mobile wallets; verification relies on submitted evidence (references, notes, attachments).

## Repository

- [github.com/rahomi/Root](https://github.com/rahomi/Root)
- **Docs**: [`SRS_Root_App_v2.pdf`](SRS_Root_App_v2.pdf) — functional requirements, workflows, and definitions.

## Contributing

1. Branch from `develop` for changes (`feature/...` or `fix/...`).
2. Open a pull request; keep commits focused and messages clear.
3. Rebase or merge `develop` before review if the branch is long-lived.

---
