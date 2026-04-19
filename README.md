# Root

Association management app for **Root**: members, capital ledger, investments, and snapshot-based profit/loss distribution.

Full requirements and workflows are documented in [`SRS_Root_App_v2.pdf`](SRS_Root_App_v2.pdf).

## Overview

Root is a financial ledger and investment allocation platform built around:

- **Authorized capital changes** (approval-driven posting)
- **Historical snapshots** (accurate allocation over time)
- **Role-based permissions** (who can submit, approve, release, close, and distribute)

Member capital submissions are created as **requests** and only affect balances after approval by authorized staff.

## MVP Scope

- **Roles**: Super Admin, Admin, and Member with permission-based actions
- **Submission requests**: Installments/capital requests with evidence (channel, optional transaction ID, notes, optional attachment)
- **Ledger operations**: Posted flow from approved requests plus admin-direct entries where policy allows (`SUBMISSION`, `WITHDRAW`, `ADJUSTMENT`)
- **Investments**: Fund release, lifecycle snapshots, close, and distribution
- **Reporting and audit**: Statements, approval queues, exports, and audit logs

## Repository Layout

Current repository structure:

- `frontend/` - frontend application workspace
- `backend/` - backend application workspace
- `README.md` - project overview and contribution notes
- `.editorconfig` - shared formatting conventions
- `.gitignore` - ignored local and build artifacts

## Getting Started

This repository is currently in scaffold stage. To start implementation:

1. Initialize `frontend/` and `backend/` with your chosen stacks.
2. Add local environment templates (`.env.example`) per workspace.
3. Document run/build/test commands for each app.
4. Keep API contracts and business rules aligned with the SRS document.

## Contributing

1. Branch from `develop` (`feature/...` or `fix/...`).
2. Keep commits focused and use clear messages.
3. Open a pull request with a short summary and test notes.
4. Rebase or merge `develop` before review for long-lived branches.
