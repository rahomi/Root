# Root Backend Documentation

## Project Stage

The backend is now in the domain-model and workflow-foundation stage. The codebase contains model definitions for:

- authentication and user management
- fine-grained permissions
- member lifecycle handling
- audit logging
- capital submission requests and attachments
- member capital ledger entries
- investments
- investment snapshots
- profit/loss distributions
- early reporting logic

What is implemented:

- Django project bootstrap and settings
- PostgreSQL-backed data model definitions across the core business modules
- custom user model and custom permission backend
- immutable audit, ledger, and snapshot patterns
- media configuration and signed-URL storage helpers for submission attachments
- basic report query logic for member statements

What is still missing or incomplete:

- real API endpoints and URL wiring beyond `/admin/`
- service layer / use-case layer for the business workflows referenced in comments
- migrations for several implemented apps
- admin customization for the current models
- full test coverage
- production settings split and deployment-ready configuration
- cleaned separation of concerns in a few places, such as report logic living in `reports/models.py`

At this stage, the backend should be described as a modeled business core with incomplete delivery surfaces.

## Current Structure

```text
backend/
├── manage.py
├── .env.example
├── DOCUMENTATION.md
├── rootBackend/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── accounts/
├── permissions/
├── members/
├── audit/
├── submissions/
├── ledger/
├── investments/
├── snapshots/
├── distributions/
└── reports/
```

Each app exists, but most are currently model-centric. Views, routes, serializers, and service orchestration are not yet implemented.

## Core Configuration

Core configuration lives in `rootBackend/settings.py`.

Current configuration highlights:

- database engine: PostgreSQL
- installed framework apps: Django admin/auth/session stack, Django REST Framework, Simple JWT
- installed local apps:
  - `accounts`
  - `permissions`
  - `members`
  - `audit`
  - `submissions`
  - `ledger`
  - `investments`
  - `distributions`
  - `snapshots`
  - `reports`
- custom user model: `accounts.User`
- custom auth backend: `accounts.backends.RootPermissionBackend`
- media storage configured with:
  - `MEDIA_ROOT = BASE_DIR / "media"`
  - `MEDIA_URL = "/media"`

Environment variables expected in `.env`:

- `SECRET_KEY`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`

## Current URL Surface

`rootBackend/urls.py` currently exposes only:

- `/admin/`

This is the main architectural gap right now: the project has substantial model design, but very little HTTP surface wired into the Django project.

## App Overview

### Accounts

The `accounts` app defines the custom authentication model and the project-level permission lookup behavior.

#### `accounts.models.User`

This is a custom Django user model based on `AbstractBaseUser` and `PermissionsMixin`.

Key fields:

- `user_id`: UUID primary key
- `full_name`: user display name
- `contact_no`: unique login identifier
- `email`: optional unique email
- `join_date`: join date
- `role`: coarse classification
- `status`: active/inactive business status
- `notes`: free-text notes
- `is_staff`: Django admin flag
- `is_active`: authentication flag
- `created_at`, `updated_at`: timestamps

Authentication settings:

- `USERNAME_FIELD = 'contact_no'`
- `REQUIRED_FIELDS = ['full_name', 'join_date']`

#### `UserRole`

Current role values:

- `SUPER_ADMIN`
- `ADMIN`
- `MEMBER`

Roles exist for classification, but the codebase is intentionally built to authorize behavior through explicit permission grants instead of role-only checks.

#### `UserStatus`

Current status values:

- `ACTIVE`
- `INACTIVE`

#### `UserManager`

`UserManager` provides:

- `create_user()`
- `create_superuser()`

#### `User.has_permission(code)`

This is the core fine-grained permission lookup helper. It checks `permissions.UserPermission` and returns `True` only if the user has a matching grant that is:

- active
- not expired, or has no expiry

#### `accounts.backends.RootPermissionBackend`

This backend overrides Django permission checks so that `user.has_perm(...)` resolves through the project permission system rather than Django’s built-in model permission tables.

Current behavior:

- rejects anonymous users
- rejects inactive users
- returns `False` for object-level permission checks
- returns `True` for Django superusers
- extracts a code like `MANAGE_USERS` from strings such as `permissions.MANAGE_USERS`
- delegates the actual lookup to `user.has_permission(code)`

### Permissions

The `permissions` app implements the fine-grained authorization model.

#### `PermissionCode`

`PermissionCode` is the enum of allowed capability identifiers.

Current values:

- `APPROVE_SUBMISSION`
- `POST_ADMIN_LEDGER`
- `CREATE_INVESTMENT`
- `RELEASE_INVESTMENT_FUNDS`
- `CLOSE_INVESTMENT`
- `DISTRIBUTE_PL`
- `REVERSE_DISTRIBUTION`
- `VIEW_ALL_REPORTS`
- `MANAGE_USERS`

#### `Permission`

`permissions.models.Permission` is the catalog of supported permissions.

Key fields:

- `permission_id`
- `code`
- `description`

Purpose:

- standardize available permission names
- provide a durable catalog for grants

#### `UserPermission`

`permissions.models.UserPermission` is the join model between a user and a permission.

Key fields:

- `user_permission_id`
- `user`
- `permission`
- `granted_by`
- `granted_at`
- `expires_at`
- `is_active`
- `revoked_by`
- `revoked_at`

Current rules:

- unique per `(user, permission)`
- supports temporary access
- supports soft revocation
- supports audit-style metadata about grant and revoke actions

#### `permissions.decorators.require_permission(code)`

This decorator protects function-based views.

Behavior:

- redirects unauthenticated users to login
- raises `PermissionDenied` if the user lacks the required permission
- allows the view to run when permission is present

### Members

The `members` app currently layers member behavior on top of the custom user model rather than introducing a separate member table.

#### `MemberProfile`

`members.models.MemberProfile` is a proxy model over `accounts.User`.

Meaning:

- it uses the same underlying database table as `accounts.User`
- it adds member-specific query behavior and lifecycle behavior
- it does not create a separate member table

Current behavior:

- `objects = ActiveMemberManager()` returns only active users
- `all_members = models.Manager()` provides unfiltered access
- `deactivate(actor)` marks the member inactive and logs the state change through the audit helper

#### `ActiveMemberManager`

This manager filters members to `status=ACTIVE`.

### Audit

The `audit` app provides immutable audit logging.

#### `AuditAction`

Current values:

- `CREATE`
- `UPDATE`
- `APPROVE`
- `REJECT`
- `RELEASE_FUNDS`
- `CLOSE`
- `DISTRIBUTE`
- `REVERSE`
- `LOGIN`
- `LOGOUT`
- `GRANT_PERM`
- `REVOKE_PERM`
- `DEACTIVATE_USER`

#### `AuditLog`

`audit.models.AuditLog` stores append-only records of critical actions.

Key fields:

- `audit_id`
- `entity_name`
- `entity_id`
- `action`
- `actor`
- `occurred_at`
- `before_json`
- `after_json`
- `reason`

Important behavior:

- records are immutable after creation
- updating an existing record raises `ValueError`
- deleting a record raises `ValueError`

#### `audit.utils.log_action(...)`

This helper creates an `AuditLog` record and is already used by member deactivation logic.

### Submissions

The `submissions` app models member capital submission requests and their supporting files.

#### Enums

Current enums:

- `RequestType`
  - `INSTALLMENT`
  - `SUBMISSION`
- `PaymentChannel`
  - `HAND_CASH`
  - `BKASH`
  - `BANK`
  - `OTHER`
- `RequestStatus`
  - `PENDING`
  - `APPROVED`
  - `REJECTED`

#### `FileAttachment`

Stores uploaded attachment metadata.

Key fields:

- `file_id`
- `uploaded_by`
- `mime_type`
- `byte_size`
- `storage_key`
- `original_filename`
- `created_at`

Important behavior:

- `get_signed_url()` returns a time-limited signed URL instead of a public URL
- the model defines `ALLOWED_MIME_TYPES`
- the model defines `MAX_BYTE_SIZE`

#### `CapitalSubmissionRequest`

This is the main request record for member capital submissions.

Key fields:

- `request_id`
- `user`
- `request_type`
- `amount`
- `requested_at`
- `txn_date`
- `payment_channel`
- `external_reference`
- `notes`
- `status`
- `reviewed_by`
- `reviewed_at`
- `rejection_reason`
- `resulting_ledger`

Important relationship:

- `resulting_ledger` is a one-to-one link to the ledger entry created when a request is approved

This establishes a clean bridge between the approval workflow and the immutable financial ledger.

#### `SubmissionAttachment`

This is the junction table between submissions and files.

Purpose:

- allow multiple files to be attached to a single submission request
- avoid embedding file fields directly in the submission record

### Submission Storage Helpers

`submissions.storage` contains helper functions for local file storage and signed access:

- `generate_signed_url()`
- `verify_signed_url()`
- `save_upload()`
- `delete_object()`

The storage layer currently assumes local media storage with HMAC-signed URLs derived from Django’s `SECRET_KEY`.

### Ledger

The `ledger` app models the immutable member capital ledger.

#### `EntryType`

Current values:

- `SUBMISSION`
- `WITHDRAW`
- `ADJUSTMENT`
- `DISTRIBUTION`
- `DISTRIBUTION_REVERSAL`

#### `ReferenceType`

Current values:

- `INVESTMENT`
- `MANUAL`
- `SYSTEM`
- `SUBMISSION_REQUEST`

#### `LedgerEntryManager`

Provides a `get_balance(user)` helper that aggregates the sum of ledger amounts for a user.

#### `MemberCapitalLedgerEntry`

This is the central financial ledger record.

Key fields:

- `ledger_id`
- `user`
- `entry_type`
- `amount`
- `currency`
- `txn_date`
- `reference_type`
- `reference_id`
- `comment`
- `created_by`
- `created_at`

Important behavior:

- entries are immutable
- updating an existing row raises `ValueError`
- deleting a row raises `ValueError`
- reversals are intended to be recorded as compensating entries, not edits

This is a strong accounting pattern and one of the more mature pieces of the current model layer.

### Investments

The `investments` app models the investment lifecycle.

#### `InvestmentType`

Current values:

- `FIXED_DEPOSIT`
- `EQUITY`
- `REAL_ESTATE`
- `LENDING`
- `OTHER`

#### `InvestmentStatus`

Current values:

- `DRAFT`
- `OPEN`
- `CLOSED`
- `DISTRIBUTED`
- `REVERSED`

#### `Investment`

Key fields:

- `investment_id`
- `title`
- `investment_type`
- `invested_to`
- `invested_amount`
- `created_date`
- `comment`
- `fund_released_at`
- `fund_released_by`
- `close_date`
- `return_amount`
- `pnl_amount`
- `closure_comment`
- `status`
- `created_by`
- `created_at`
- `updated_at`

The model comments indicate a segregation-of-duties rule:

- the user who creates an investment should not be the one who releases its funds

That rule is documented in comments as a service-layer enforcement point, which means the business rule is planned but not enforced directly in the model itself.

### Snapshots

The `snapshots` app stores frozen capital ownership data at the moment an investment opens.

#### `InvestmentSnapshotHeader`

Key fields:

- `snapshot_id`
- `investment`
- `total_capital`
- `member_count`
- `snapshot_time`
- `created_by`

Important behavior:

- one-to-one with `Investment`
- immutable after creation

#### `InvestmentSnapshotLine`

Key fields:

- `snapshot_line_id`
- `snapshot`
- `user`
- `capital_at_snapshot`
- `ratio`

Important behavior:

- immutable after creation
- unique per `(snapshot, user)`

Purpose:

- freeze member capital ratios at a point in time
- ensure later distributions are based on stored ratios, not recomputed live balances

### Distributions

The `distributions` app models profit/loss posting and reversal.

#### `DistributionStatus`

Current values:

- `POSTED`
- `REVERSED`

#### `InvestmentDistribution`

Key fields:

- `distribution_id`
- `investment`
- `snapshot`
- `pnl_amount`
- `rounded_total`
- `remainder_applied`
- `status`
- `posted_by`
- `posted_at`
- `reversed_by`
- `reversed_at`

Important rule:

- a conditional unique constraint allows only one `POSTED` distribution per investment

This is an important idempotency safeguard at the database level.

#### `InvestmentDistributionLine`

Key fields:

- `distribution_line_id`
- `distribution`
- `user`
- `ratio_used`
- `share_amount`
- `ledger_entry`

Purpose:

- record each member’s share of a distribution
- connect the distribution calculation to the actual ledger impact

### Reports

The `reports` app is currently partial and inconsistent.

Observed state:

- `reports/views.py` is still the default stub
- `reports/models.py` contains report query/view logic instead of models

That logic currently defines `member_statement(request)`, which:

- requires login
- loads a member’s ledger entries
- loads pending submission requests separately
- computes current balance from ledger sums
- renders `reports/member_statement.html`

This should eventually be moved to a proper view module, but it is still useful as proof that cross-app reporting logic has started.

## Current Cross-App Relationships

The current backend already has meaningful relationships across apps:

```text
accounts.User
  ├── permissions.UserPermission.user
  ├── permissions.UserPermission.granted_by
  ├── permissions.UserPermission.revoked_by
  ├── audit.AuditLog.actor
  ├── submissions.FileAttachment.uploaded_by
  ├── submissions.CapitalSubmissionRequest.user
  ├── submissions.CapitalSubmissionRequest.reviewed_by
  ├── ledger.MemberCapitalLedgerEntry.user
  ├── ledger.MemberCapitalLedgerEntry.created_by
  ├── investments.Investment.created_by
  ├── investments.Investment.fund_released_by
  ├── snapshots.InvestmentSnapshotHeader.created_by
  ├── snapshots.InvestmentSnapshotLine.user
  ├── distributions.InvestmentDistribution.posted_by
  ├── distributions.InvestmentDistribution.reversed_by
  └── distributions.InvestmentDistributionLine.user

permissions.Permission
  └── permissions.UserPermission.permission

members.MemberProfile
  └── proxy of accounts.User

submissions.CapitalSubmissionRequest
  ├── one-to-one -> ledger.MemberCapitalLedgerEntry
  └── one-to-many -> submissions.SubmissionAttachment

submissions.FileAttachment
  └── linked by submissions.SubmissionAttachment

investments.Investment
  ├── one-to-one -> snapshots.InvestmentSnapshotHeader
  └── one-to-many -> distributions.InvestmentDistribution

snapshots.InvestmentSnapshotHeader
  └── one-to-many -> snapshots.InvestmentSnapshotLine

distributions.InvestmentDistribution
  └── one-to-many -> distributions.InvestmentDistributionLine

distributions.InvestmentDistributionLine
  └── foreign key -> ledger.MemberCapitalLedgerEntry
```

This is the clearest sign that the project has progressed from a basic scaffold into a connected financial domain model.

## Workflow Direction

The comments and model design imply the following workflow architecture:

### Submission Flow

1. A member creates a `CapitalSubmissionRequest`
2. Optional files are attached through `SubmissionAttachment`
3. The request remains `PENDING`
4. On approval, a `MemberCapitalLedgerEntry` is created
5. The request links to that ledger entry through `resulting_ledger`

### Investment Flow

1. A finance user creates an `Investment` in `DRAFT`
2. A different authorized user releases funds
3. When the investment opens, a frozen `InvestmentSnapshotHeader` and related lines are created
4. On closure, return and P/L information are captured
5. Distribution logic later uses the stored snapshot ratios

### Distribution Flow

1. A distribution is posted against an `Investment` and its `snapshot`
2. Member shares are stored in `InvestmentDistributionLine`
3. Each line links to an actual ledger entry
4. Reversal is modeled as a new reversal state / compensating pattern rather than editing history

### Reporting Flow

1. Member balance is derived from the immutable ledger
2. Pending submission requests are shown separately
3. Report calculations are cross-app queries, not separate persisted totals

## Maturity Assessment

The current backend has solid modeling decisions in a few important areas:

- custom auth model instead of retrofitting later
- explicit fine-grained permissions
- append-only audit logging
- immutable financial ledger
- frozen investment snapshots for historical correctness
- conditional uniqueness for active distributions

The main immaturity is not the data model. It is the missing execution layer around the model design:

- almost no endpoints
- almost no services
- almost no workflow orchestration
- very limited test coverage
- partial placement issues in `reports`

## Known Gaps

Most important gaps at the current stage:

- create real migrations for the implemented apps
- seed `Permission` data
- add services for submission approval, investment release, snapshot capture, closure, and distribution posting
- wire URL patterns and implement real views or APIs
- move report logic out of `reports/models.py`
- register and customize the models in Django admin
- add validation beyond comments where critical business rules exist
- add automated tests for immutability, constraints, and workflow transitions

## Suggested Next Steps

Recommended near-term sequence:

1. Freeze the current data model with migrations
2. Add seed data for permission codes
3. Implement service-layer workflows for submissions, investments, snapshots, and distributions
4. Add serializers and API views
5. Wire URLs for the first usable endpoints
6. Add tests around the immutable models and cross-app constraints
7. Refactor `reports` into a normal Django app structure

## Summary

The backend is no longer just a scaffold with auth and permissions. It now contains a real financial-domain model spanning:

- user and permission management
- member lifecycle operations
- audit logging
- capital submission requests and file attachments
- immutable ledger posting
- investment lifecycle tracking
- frozen ownership snapshots
- profit/loss distributions
- early report logic

The project is still incomplete from an API and workflow-delivery perspective, but the model layer already represents a serious backend foundation.
