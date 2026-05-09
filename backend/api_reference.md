# PHASE 1: # Auth API Reference ✅ Done

Base URL: `/api/`
All protected endpoints require: `Authorization: Bearer <access_token>`

---

## POST /api/auth/login/ ✅ implemented
**Public**

Request:
```json
{ "contact_no": "01700000000", "password": "secret123" }
```
Response `200`:
```json
{
  "access": "<jwt_access_token>",
  "refresh": "<jwt_refresh_token>",
  "user": {
    "user_id": "uuid",
    "full_name": "Rahim Uddin",
    "contact_no": "01700000000",
    "email": "rahim@example.com",
    "role": "MEMBER",
    "status": "ACTIVE"
  }
}
```
Errors: `400` invalid credentials / inactive account

---

## POST /api/auth/token/refresh/  ✅ implemented
**Public** (needs valid refresh token)

Request:
```json
{ "refresh": "<jwt_refresh_token>" }
```
Response `200`:
```json
{ "access": "<new_access_token>", "refresh": "<new_refresh_token>" }
```
Note: old refresh token is blacklisted (ROTATE_REFRESH_TOKENS = True)

---

## POST /api/auth/logout/ ✅ implemented
**Authenticated**

Request:
```json
{ "refresh": "<jwt_refresh_token>" }
```
Response `200`:
```json
{ "detail": "Successfully logged out." }
```

---

## POST /api/auth/change-password/ ✅ implemented
**Authenticated** (self only)

Request:
```json
{
  "current_password": "old_secret",
  "new_password": "new_secret_123",
  "confirm_password": "new_secret_123"
}
```
Response `200`:
```json
{ "detail": "Password changed successfully." }
```
Errors: `400` wrong current password / passwords don't match / weak password

---

## GET /api/auth/me/ ✅ implemented
**Authenticated** — returns current user's profile

Response `200`:
```json
{
  "user_id": "uuid",
  "full_name": "Rahim Uddin",
  "contact_no": "01700000000",
  "email": "rahim@example.com",
  "join_date": "2024-01-15",
  "role": "MEMBER",
  "status": "ACTIVE",
  "notes": "",
  "created_at": "...",
  "updated_at": "..."
}
```

## PATCH /api/auth/me/
**Authenticated** — update own profile (no role/status changes)

Request (all fields optional):
```json
{
  "full_name": "Rahim Uddin Khan",
  "email": "new@example.com",
  "contact_no": "01711111111",
  "notes": "updated notes"
}
```

---

## POST /api/users/ ✅ implemented
**Requires: MANAGE_USERS**

Request:
```json
{
  "full_name": "Karim Miah",
  "contact_no": "01800000000",
  "email": "karim@example.com",
  "join_date": "2024-06-01",
  "role": "MEMBER",
  "notes": "",
  "password": "initial_pass_123"
}
```
Response `201`: Full user object (same shape as GET /api/auth/me/)

---

## GET /api/users/ ✅ implemented
**Requires: MANAGE_USERS**

Query params:
- `status=ACTIVE|INACTIVE`
- `role=SUPER_ADMIN|ADMIN|MEMBER`
- `search=<name substring>`

Response `200`: Array of user objects

---

## GET /api/users/{user_id}/  ✅ implemented
**Self or MANAGE_USERS**

Response `200`: Full user object

---

## PATCH /api/users/{user_id}/ ✅ implemented
**Self** → can update: full_name, email, contact_no, notes
**MANAGE_USERS** → can also update: role, status, join_date

---

## DELETE /api/users/{user_id}/ ✅ implemented
**Requires: MANAGE_USERS** (soft deactivate only, cannot deactivate self)

Response `200`:
```json
{ "detail": "User 'Karim Miah' has been deactivated." }
```

---

## Error shape (all endpoints)
```json
{
  "detail": "Human-readable summary.",
  "errors": {
    "field_name": ["Validation message."]
  }
}
```
`errors` is `null` for non-field errors (auth failures, 403s, 404s).


# PHASE 2 — API Reference Submisssions and Ledgers ✅ Done

Base URL: `/api/`
All endpoints require: `Authorization: Bearer <access_token>`

---

## Submissions

### POST /api/submission/ ✅ implemented
Create a capital submission request. Member only.

Request:
```json
{
  "request_type":      "INSTALLMENT",
  "amount":            "5000.00",
  "txn_date":          "2024-06-15",
  "payment_channel":   "BKASH",
  "external_reference": "TXN123456789",
  "notes":             "June installment"
}
```
`request_type` options: `INSTALLMENT`, `SUBMISSION`
`payment_channel` options: `HAND_CASH`, `BKASH`, `BANK`, `OTHER`

Response `201`: Full submission object with `status: "PENDING"`

---

### GET /api/submission/ ✅ implemented
Member's own submission. Query params: `?status=PENDING|APPROVED|REJECTED`

Response `200`: Array of submission objects

---

### GET /api/submission/{request_id}/ ✅ implemented
Single submission detail. Member sees own, staff with `APPROVE_SUBMISSION` sees all.

---

### POST /api/submission/{request_id}/attachments/
Upload a file to a PENDING submission. Multipart form data.
Only the submitting member can upload.

Request: `Content-Type: multipart/form-data`
Field: `file` (jpeg / png / pdf, max 5 MB)

Response `201`:
```json
{
  "file_id": "uuid",
  "original_filename": "receipt.pdf",
  "mime_type": "application/pdf",
  "byte_size": 204800,
  "created_at": "...",
  "signed_url": "/media/serve/attachments/.../receipt.pdf?expires=...&sig=..."
}
```

---

### GET /api/submission/queue/ ✅ implemented
Pending approval queue. Requires `APPROVE_SUBMISSION`.
Query params: `?payment_channel=HAND_CASH|BKASH|BANK|OTHER`

Response `200`:
```json
{
  "count": 3,
  "results": [
    {
      "request_id": "uuid",
      "member_name": "Rahim Uddin",
      "member_contact": "01800000000",
      "request_type": "INSTALLMENT",
      "amount": "5000.00",
      "payment_channel": "BKASH",
      "external_reference": "TXN123456789",
      "notes": "June installment",
      "requested_at": "...",
      "attachment_count": 1,
      "attachments": [...]
    }
  ]
}
```

---

### GET /api/submission/history/ ✅ implemented
Reviewed submission history. Returns `APPROVED` and `REJECTED` submissions.

- Users with `APPROVE_SUBMISSION` see all reviewed submissions.
- Members without `APPROVE_SUBMISSION` see only their own reviewed submissions.

Query params:
- `?status=APPROVED|REJECTED`
- `?request_type=INSTALLMENT|SUBMISSION`
- `?user_id=<uuid>` for admin member profile history

Response `200`:
```json
{
  "count": 3,
  "results": [
    {
      "request_id": "uuid",
      "member_name": "Sabbir Rahman",
      "member_contact": "01700000000",
      "request_type": "INSTALLMENT",
      "amount": "8000.00",
      "txn_date": "2026-04-17",
      "payment_channel": "BKASH",
      "external_reference": "TXN123456789",
      "status": "APPROVED",
      "reviewed_at": "2026-04-17T10:30:00Z",
      "reviewed_by": {
        "user_id": "uuid",
        "full_name": "Admin User"
      },
      "rejection_reason": ""
    }
  ]
}
```

---

### POST /api/submission/{request_id}/approve/ ✅ implemented
Approve a PENDING request. Requires `APPROVE_SUBMISSION`.
Body: `{}` (empty)

Response `200`: Updated submission object with `status: "APPROVED"` and `resulting_ledger_id` set.

---

### POST /api/submission/{request_id}/reject/ ✅ implemented
Reject a PENDING request. Requires `APPROVE_SUBMISSION`.

Request:
```json
{ "rejection_reason": "Payment reference could not be verified." }
```

Response `200`: Updated submission with `status: "REJECTED"`

---

## Ledger

### GET /api/ledger/ ✅ implemented
Member's own ledger statement.

Query params:
- `?entry_type=SUBMISSION|WITHDRAW|ADJUSTMENT|DISTRIBUTION|DISTRIBUTION_REVERSAL`
- `?from_date=YYYY-MM-DD`
- `?to_date=YYYY-MM-DD`

Response `200`:
```json
{
  "current_balance": "15000.00",
  "pending_total":   "5000.00",
  "entry_count": 3,
  "entries": [
    {
      "ledger_id": "uuid",
      "entry_type": "SUBMISSION",
      "amount": "5000.00",
      "currency": "BDT",
      "txn_date": "2024-06-15",
      "reference_type": "SUBMISSION_REQUEST",
      "reference_id": "uuid",
      "comment": "Approved Installment via bKash",
      "created_by_name": "Admin User",
      "created_at": "..."
    }
  ]
}
```
Note: `current_balance` reflects posted entries only (BR-06).
`pending_total` is informational — pending requests are NOT in the balance.

---

### GET /api/ledger/members/{user_id}/ ✅ implemented
Any member's ledger. Requires `VIEW_ALL_REPORTS`.
Same response shape as above, plus user info at the top.

---

### GET /api/ledger/admin/ ✅ implemented
All member ledger entries for the admin ledger screen. Requires `VIEW_ALL_REPORTS`.

Query params:
- `?entry_type=SUBMISSION|WITHDRAW|ADJUSTMENT|DISTRIBUTION|DISTRIBUTION_REVERSAL`
- `?from_date=YYYY-MM-DD`
- `?to_date=YYYY-MM-DD`
- `?user_id=<uuid>`

Response `200`:
```json
{
  "total_in": "45500.00",
  "total_out": "5000.00",
  "entry_count": 4,
  "entries": [
    {
      "ledger_id": "uuid",
      "user_id": "uuid",
      "member_name": "Sabbir Rahman",
      "member_contact": "01700000000",
      "entry_type": "SUBMISSION",
      "amount": "8000.00",
      "currency": "BDT",
      "txn_date": "2026-04-17",
      "reference_type": "SUBMISSION_REQUEST",
      "reference_id": "SR003",
      "comment": "Hand Cash",
      "created_by_name": "Admin User",
      "created_at": "..."
    }
  ]
}
```

---

### POST /api/ledger/admin-post/ ✅ implemented
Admin-direct ledger entry. Requires `POST_ADMIN_LEDGER`.

Request:
```json
{
  "contact_no":   "01700000000",
  "entry_type":   "ADJUSTMENT",
  "amount":       "-500.00",
  "txn_date":     "2024-06-20",
  "comment":      "Correction for duplicate entry",
  "reference_id": ""
}
```
Use `contact_no` for admin UI posting. `user_id` is also supported for existing clients; if both are sent, they must refer to the same member.

`entry_type` allowed values: `SUBMISSION`, `WITHDRAW`, `ADJUSTMENT`
`amount` sign convention:
- `SUBMISSION`: must be positive
- `WITHDRAW`: must be negative
- `ADJUSTMENT`: positive or negative

Response `201`:
```json
{
  "entry": { ...ledger entry object... },
  "new_balance": "14500.00"
}
```


# Phase 3 — API Reference: Investments & Snapshots

Base URL: `/api/investments/`
All endpoints require: `Authorization: Bearer <access_token>`

---

## POST /api/investments/
Create an investment in DRAFT. Requires `CREATE_INVESTMENT`.

Request:
```json
{
  "title":           "Padma Bank FDR — Q3 2024",
  "investment_type": "FIXED_DEPOSIT",
  "invested_to":     "Padma Bank Ltd.",
  "invested_amount": "500000.00",
  "created_date":    "2024-07-01",
  "comment":         "12-month FDR at 8.5% p.a."
}
```
`investment_type` options:
`FIXED_DEPOSIT`, `EQUITY`, `REAL_ESTATE`, `LENDING`, `OTHER`

Response `201`:
```json
{
  "investment_id":     "uuid",
  "title":             "Padma Bank FDR — Q3 2024",
  "investment_type":   "FIXED_DEPOSIT",
  "invested_to":       "Padma Bank Ltd.",
  "invested_amount":   "500000.00",
  "created_date":      "2024-07-01",
  "comment":           "12-month FDR at 8.5% p.a.",
  "status":            "DRAFT",
  "fund_released_at":  null,
  "fund_released_by":  null,
  "close_date":        null,
  "return_amount":     null,
  "pnl_amount":        null,
  "closure_comment":   "",
  "has_snapshot":      false,
  "created_by":        { "user_id": "uuid", "full_name": "Finance Manager" },
  "created_at":        "2024-07-01T10:00:00Z",
  "updated_at":        "2024-07-01T10:00:00Z"
}
```

---

## GET /api/investments/
List all investments. Any authenticated user.

Query params:
- `?status=DRAFT|OPEN|CLOSED|DISTRIBUTED|REVERSED`
- `?investment_type=FIXED_DEPOSIT|EQUITY|REAL_ESTATE|LENDING|OTHER`

Response `200`: Array of compact investment objects.

---

## GET /api/investments/{investment_id}/
Full investment detail. Any authenticated user.

Response `200`: Full investment object (same shape as POST response).

---

## PATCH /api/investments/{investment_id}/
Edit a DRAFT investment. Requires `CREATE_INVESTMENT`.
Returns `400` if investment is not in DRAFT status.

Request (all fields optional):
```json
{
  "title":           "Updated Title",
  "invested_amount": "600000.00",
  "comment":         "Revised amount after board approval"
}
```

---

## POST /api/investments/{investment_id}/release-funds/
Transition DRAFT → OPEN. Requires `RELEASE_INVESTMENT_FUNDS`.
Atomically captures the member capital snapshot at this moment.

Request: `{}` (empty body)

Business rules enforced:
- Investment must be DRAFT.
- Actor ≠ creator (segregation of duties).
- At least one member must have positive authorized capital.
- Snapshot sum(ratio) = 1.0 verified before committing.

Response `200`: Updated investment with `status: "OPEN"` and `has_snapshot: true`

Errors:
- `400` — not DRAFT / creator attempting to release / zero capital
- `403` — missing permission

---

## POST /api/investments/{investment_id}/close/
Transition OPEN → CLOSED. Requires `CLOSE_INVESTMENT`.

Request:
```json
{
  "return_amount":   "534500.00",
  "close_date":      "2024-07-31",
  "closure_comment": "FDR matured. Principal + interest received."
}
```
`closure_comment` is optional.

Response `200`: Updated investment with:
```json
{
  "status":        "CLOSED",
  "return_amount": "534500.00",
  "pnl_amount":    "34500.00",
  "close_date":    "2024-07-31"
}
```
PnL is automatically computed: `return_amount - invested_amount`
Negative PnL (loss) is valid.

---

## GET /api/investments/{investment_id}/snapshot/
View the frozen member capital ratios. Any authenticated user.
Only available after `release-funds/` has been called (status OPEN or beyond).

Response `200`:
```json
{
  "snapshot_id":   "uuid",
  "investment_id": "uuid",
  "total_capital": "220000.00",
  "member_count":  3,
  "snapshot_time": "2024-07-01T10:05:00Z",
  "created_by":    { "user_id": "uuid", "full_name": "Accounts Manager" },
  "lines": [
    {
      "user_id":             "uuid",
      "full_name":           "Rahim Uddin",
      "capital_at_snapshot": "110000.00",
      "ratio":               "0.5000000000",
      "ratio_percent":       50.0
    },
    {
      "user_id":             "uuid",
      "full_name":           "Karim Miah",
      "capital_at_snapshot": "60000.00",
      "ratio":               "0.2727272727",
      "ratio_percent":       27.27272727
    },
    {
      "user_id":             "uuid",
      "full_name":           "Salam Ahmed",
      "capital_at_snapshot": "50000.00",
      "ratio":               "0.2272727273",
      "ratio_percent":       22.72727273
    }
  ]
}
```

---

## Full lifecycle example

```bash
# 1. Finance creates investment (DRAFT)
http POST /api/investments/ "Authorization: Bearer $FINANCE_TOKEN" \
  title="Padma Bank FDR" investment_type=FIXED_DEPOSIT \
  invested_to="Padma Bank" invested_amount=500000.00 \
  created_date=2024-07-01

INVESTMENT_ID="<uuid from response>"

# 2. Edit while still DRAFT
http PATCH /api/investments/$INVESTMENT_ID/ "Authorization: Bearer $FINANCE_TOKEN" \
  comment="Board approved on 2024-07-02"

# 3. Accounts releases funds — MUST be a different user than Finance
http POST /api/investments/$INVESTMENT_ID/release-funds/ \
  "Authorization: Bearer $ACCOUNTS_TOKEN"
# → status becomes OPEN, snapshot captured

# 4. View snapshot to verify ratios
http GET /api/investments/$INVESTMENT_ID/snapshot/ \
  "Authorization: Bearer $ADMIN_TOKEN"

# 5. Closer enters return amount after maturity
http POST /api/investments/$INVESTMENT_ID/close/ \
  "Authorization: Bearer $CLOSER_TOKEN" \
  return_amount=534500.00 close_date=2024-07-31 \
  closure_comment="FDR matured"
# → status becomes CLOSED, pnl_amount = 34500.00

# 6. Verify PnL in detail
http GET /api/investments/$INVESTMENT_ID/ \
  "Authorization: Bearer $ADMIN_TOKEN"
```

---

## State machine

```
DRAFT ──[release-funds]──► OPEN ──[close]──► CLOSED ──[distribute]──► DISTRIBUTED
                                                              │
                                                        [reverse]
                                                              ▼
                                                          REVERSED ──[redistribute]──► DISTRIBUTED
```

Distribute and Reverse are Phase 4.

---

## Common errors

| Error | Cause |
|---|---|
| `400` "not DRAFT" on release | Already released or closed |
| `400` "segregation of duties" | Creator trying to release own investment |
| `400` "no positive capital" | No approved submissions exist yet |
| `400` "not OPEN" on close | Already closed or still DRAFT |
| `400` "return_amount negative" | Negative return — use 0.00 for total loss |
| `403` | Missing required permission |


# Phase 4 — API Reference: Distribution Engine

Base URL: `/api/investments/`
All endpoints require: `Authorization: Bearer <access_token>`

---

## POST /api/investments/{investment_id}/distribute/
Distribute P/L to all members. Requires `DISTRIBUTE_PL`.

Prerequisites:
- Investment status must be `CLOSED`.
- A snapshot must exist (captured at `OPEN` transition).

Request: `{}` (empty — all data derived from investment and snapshot)

**Calculation (§4.3–4.4):**
```
rawShare(member) = snapshotRatio × investmentPnL
roundedShare     = round(rawShare, 2dp, HALF_UP)
roundedTotal     = sum(roundedShare for all members)
remainder        = investmentPnL - roundedTotal
→ remainder applied to highest-capital member (lowest user_id on tie)
```

Response `201`:
```json
{
  "distribution_id":   "uuid",
  "investment_id":     "uuid",
  "snapshot_id":       "uuid",
  "pnl_amount":        "34500.00",
  "rounded_total":     "34500.00",
  "remainder_applied": "0.00",
  "status":            "POSTED",
  "posted_by":         { "user_id": "uuid", "full_name": "Finance Manager" },
  "posted_at":         "2024-08-01T09:00:00Z",
  "reversed_by":       null,
  "reversed_at":       null,
  "lines": [
    {
      "distribution_line_id": "uuid",
      "user_id":              "uuid",
      "full_name":            "Rahim Uddin",
      "ratio_used":           "0.5000000000",
      "share_amount":         "17250.00",
      "ledger_entry_id":      "uuid"
    },
    {
      "distribution_line_id": "uuid",
      "user_id":              "uuid",
      "full_name":            "Karim Miah",
      "ratio_used":           "0.2727272727",
      "share_amount":         "9409.09",
      "ledger_entry_id":      "uuid"
    },
    {
      "distribution_line_id": "uuid",
      "user_id":              "uuid",
      "full_name":            "Salam Ahmed",
      "ratio_used":           "0.2272727273",
      "share_amount":         "7840.91",
      "ledger_entry_id":      "uuid"
    }
  ]
}
```

Investment status advances to `DISTRIBUTED`.
Members' ledger balances are updated (positively for profit, negatively for loss).

**Worked example (§4.5–4.6):**
```
Snapshot: A=11000, B=6000, C=5000  Total=22000
PnL = +500

rawShare(A) = 11000/22000 × 500 = 250.00
rawShare(B) =  6000/22000 × 500 = 136.36 (136.3636...)
rawShare(C) =  5000/22000 × 500 = 113.64 (113.6363...)

roundedTotal = 500.00  remainder = 0.00

Loss example (PnL = -350):
rawShare(A) = -175.00
rawShare(B) =  -95.45
rawShare(C) =  -79.55
→ negative ledger entries reduce each member's balance
```

Errors:
- `400` — not CLOSED / already distributed / no snapshot / no members
- `403` — missing DISTRIBUTE_PL permission

---

## GET /api/investments/{investment_id}/distribution/
View distribution record(s). Any authenticated user.

Query params: `?status=POSTED|REVERSED`

Returns array (most recent first). A single investment may have:
- 0 entries (never distributed)
- 1 entry with `status: POSTED` (active distribution)
- 1 entry with `status: REVERSED` + 1 with `status: POSTED` (after reversal + re-distribution)

Response `200`: Array of distribution objects (same shape as POST response)
Response `404`: No distribution exists yet

---

## POST /api/investments/{investment_id}/reverse/
Reverse a posted distribution. Requires `REVERSE_DISTRIBUTION`.

Prerequisites:
- Investment status must be `DISTRIBUTED`.
- A `POSTED` distribution must exist.

Request:
```json
{
  "reason": "Incorrect return amount entered. Will re-distribute after correction."
}
```

**What happens internally:**
1. For each original distribution line, a new `DISTRIBUTION_REVERSAL` ledger entry
   is created with the negated `share_amount`.
2. Original ledger entries are **never modified or deleted** (append-only ledger).
3. The distribution record is marked `REVERSED`.
4. Investment status returns to `CLOSED` — enabling one re-distribution.

Response `200`: The reversed distribution object with `status: REVERSED`

```json
{
  "distribution_id": "uuid",
  "status":          "REVERSED",
  "reversed_by":     { "user_id": "uuid", "full_name": "Super Admin" },
  "reversed_at":     "2024-08-02T11:00:00Z",
  "lines": [ ... original lines unchanged ... ]
}
```

After reversal, each member's ledger will show:
```
DISTRIBUTION         +17250.00   (original)
DISTRIBUTION_REVERSAL -17250.00  (compensating)
Net effect = 0.00
```

Errors:
- `400` — not DISTRIBUTED / no POSTED distribution found
- `403` — missing REVERSE_DISTRIBUTION permission

---

## Full Phase 4 test sequence

```bash
# Prerequisites: investment created, opened, members have capital, closed
# Investment status: CLOSED, pnl_amount set

# 1. Distribute P/L
http POST /api/investments/$INVESTMENT_ID/distribute/ \
  "Authorization: Bearer $FINANCE_TOKEN"
# → 201, status=DISTRIBUTED, lines show each member's share

# 2. Verify member balances updated in ledger
http GET /api/ledger/ "Authorization: Bearer $MEMBER_TOKEN"
# → current_balance increased by member's share (profit)
#   or decreased (loss)

# 3. Try distributing again — must be blocked
http POST /api/investments/$INVESTMENT_ID/distribute/ \
  "Authorization: Bearer $FINANCE_TOKEN"
# → 400 "A distribution has already been posted"

# 4. View distribution detail
http GET /api/investments/$INVESTMENT_ID/distribution/ \
  "Authorization: Bearer $ADMIN_TOKEN"

# 5. Reverse the distribution
http POST /api/investments/$INVESTMENT_ID/reverse/ \
  "Authorization: Bearer $SUPER_ADMIN_TOKEN" \
  reason="Wrong return amount. Correcting and re-distributing."
# → 200, distribution status=REVERSED, investment back to CLOSED

# 6. Verify member balances zeroed out (original + reversal = 0)
http GET /api/ledger/ "Authorization: Bearer $MEMBER_TOKEN"

# 7. Fix the investment return amount (close again with correct value)
#    Note: investment is now CLOSED again — can be re-distributed
http POST /api/investments/$INVESTMENT_ID/distribute/ \
  "Authorization: Bearer $FINANCE_TOKEN"
# → 201, fresh distribution with corrected amounts

# 8. Loss distribution test — close a different investment at a loss
#    pnl_amount will be negative → member balances reduced
```

---

## State after Phase 4

```
DRAFT ──[release-funds]──► OPEN ──[close]──► CLOSED ──[distribute]──► DISTRIBUTED
                                                  ▲                         │
                                                  │                    [reverse]
                                                  └────────────────────────┘
                                              (back to CLOSED, re-distribute once)
```

## Common errors

| Error | Cause |
|---|---|
| `400` not CLOSED | Tried to distribute before closing |
| `400` already distributed | Second distribute before reversing |
| `400` not DISTRIBUTED | Tried to reverse a non-distributed investment |
| `400` no POSTED distribution | Distribution already reversed |
| `400` no snapshot | Investment was never opened (data integrity issue) |
| `403` | Missing DISTRIBUTE_PL or REVERSE_DISTRIBUTION |


# Phase 5 — API Reference: Reports & Exports

Base URL: `/api/reports/`
All endpoints require: `Authorization: Bearer <access_token>`

---

## Member Self-Service

### GET /api/reports/my-statement/
Own ledger statement with running balance per row.

Query params:
- `?from_date=YYYY-MM-DD`
- `?to_date=YYYY-MM-DD`
- `?entry_type=SUBMISSION|WITHDRAW|ADJUSTMENT|DISTRIBUTION|DISTRIBUTION_REVERSAL`

Response `200`:
```json
{
  "member": {
    "user_id": "uuid", "full_name": "Rahim Uddin",
    "contact_no": "01800000000", "join_date": "2024-01-15"
  },
  "current_balance": "22750.00",
  "pending_total":   "5000.00",
  "entry_count": 4,
  "entries": [
    {
      "ledger_id": "uuid",
      "entry_type": "SUBMISSION",
      "amount": "5000.00",
      "currency": "BDT",
      "txn_date": "2024-06-15",
      "running_balance": "5000.00",
      "reference_type": "SUBMISSION_REQUEST",
      "reference_id": "uuid",
      "comment": "Approved Installment via bKash",
      "created_at": "...",
      "created_by__full_name": "Admin User"
    },
    {
      "entry_type": "DISTRIBUTION",
      "amount": "17250.00",
      "running_balance": "22250.00",
      ...
    }
  ],
  "pending_requests": [
    {
      "request_id": "uuid",
      "request_type": "INSTALLMENT",
      "amount": "5000.00",
      "payment_channel": "BKASH",
      "requested_at": "..."
    }
  ]
}
```
Note: `current_balance` is always the full balance (ignores date filters).
`pending_total` is informational — pending requests are NOT in the balance.

---

### GET /api/reports/my-distributions/
Own distribution history across all investments.

Response `200`:
```json
{
  "total_received": "17250.00",
  "distribution_count": 1,
  "distributions": [
    {
      "distribution_id":     "uuid",
      "investment_id":       "uuid",
      "investment_title":    "Padma Bank FDR",
      "investment_type":     "FIXED_DEPOSIT",
      "pnl_amount":          "34500.00",
      "distribution_status": "POSTED",
      "ratio_used":          "0.5000000000",
      "share_amount":        "17250.00",
      "posted_at":           "2024-08-01T09:00:00Z",
      "posted_by":           "Finance Manager",
      "ledger_entry_id":     "uuid"
    }
  ]
}
```

---

## Staff Reports (require `VIEW_ALL_REPORTS`)

### GET /api/reports/association-summary/
High-level financial snapshot of the entire association.

Response `200`:
```json
{
  "generated_at": "2024-08-15T10:00:00Z",
  "capital": {
    "total_authorized": "220000.00",
    "total_pending":     "15000.00",
    "total_invested":    "500000.00"
  },
  "members": {
    "total": 5, "active": 4, "inactive": 1
  },
  "investments": {
    "total": 3, "draft": 0, "open": 1,
    "closed": 0, "distributed": 1, "reversed": 1
  },
  "distributions": {
    "total_pnl_distributed": "34500.00"
  },
  "submissions": {
    "total": 12, "pending": 3, "approved": 8, "rejected": 1
  }
}
```

---

### GET /api/reports/member-balances/
All members with current authorized balance.

Query params: `?status=ACTIVE|INACTIVE`  `?search=<name>`

Response `200`:
```json
{
  "total_capital": "220000.00",
  "member_count": 4,
  "members": [
    {
      "user_id": "uuid", "full_name": "Rahim Uddin",
      "contact_no": "01800000000", "email": "...",
      "join_date": "2024-01-15", "role": "MEMBER",
      "status": "ACTIVE", "balance": "72250.00"
    }
  ]
}
```

---

### GET /api/reports/investment-register/
All investments with financial summary.

Query params:
- `?status=DRAFT|OPEN|CLOSED|DISTRIBUTED|REVERSED`
- `?investment_type=FIXED_DEPOSIT|EQUITY|REAL_ESTATE|LENDING|OTHER`

Response `200`:
```json
{
  "investment_count": 2,
  "investments": [
    {
      "investment_id":   "uuid",
      "title":           "Padma Bank FDR",
      "investment_type": "FIXED_DEPOSIT",
      "invested_to":     "Padma Bank Ltd.",
      "invested_amount": "500000.00",
      "return_amount":   "534500.00",
      "pnl_amount":      "34500.00",
      "created_date":    "2024-07-01",
      "close_date":      "2024-07-31",
      "status":          "DISTRIBUTED",
      "member_count":    3,
      "created_by":      "Finance Manager",
      "fund_released_by": "Accounts Manager",
      "fund_released_at": "2024-07-01T10:05:00Z"
    }
  ]
}
```

---

### GET /api/reports/distribution-logs/
All distributions with POSTED/REVERSED status.

Query params: `?status=POSTED|REVERSED`  `?investment_id=<uuid>`

Response `200`:
```json
{
  "distribution_count": 2,
  "distributions": [
    {
      "distribution_id":   "uuid",
      "investment_title":  "Padma Bank FDR",
      "pnl_amount":        "34500.00",
      "rounded_total":     "34500.00",
      "remainder_applied": "0.00",
      "status":            "POSTED",
      "posted_by":         "Finance Manager",
      "posted_at":         "2024-08-01T09:00:00Z",
      "reversed_by":       null,
      "reversed_at":       null,
      "member_count":      3
    }
  ]
}
```

---

### GET /api/reports/approval-queue-report/
All pending submission requests summarised by payment channel.

Response `200`:
```json
{
  "total_pending_amount": "15000.00",
  "total_pending_count":  3,
  "by_channel": {
    "BKASH":     { "count": 2, "total_amount": "10000.00" },
    "HAND_CASH": { "count": 1, "total_amount":  "5000.00" }
  },
  "items": [
    {
      "request_id":        "uuid",
      "member_name":       "Karim Miah",
      "member_contact":    "01900000000",
      "request_type":      "INSTALLMENT",
      "amount":            "5000.00",
      "txn_date":          "2024-08-10",
      "payment_channel":   "BKASH",
      "external_reference": "TXN987654321",
      "notes":             "",
      "requested_at":      "2024-08-10T08:00:00Z",
      "attachment_count":  1
    }
  ]
}
```

---

## CSV Exports (require `VIEW_ALL_REPORTS`)

All exports return `Content-Type: text/csv` with streaming response.
Download via browser or:
```bash
http GET /api/reports/export/member-balances/ \
  "Authorization: Bearer $TOKEN" > member_balances.csv
```

### GET /api/reports/export/member-balances/
Columns: `user_id, full_name, contact_no, email, join_date, role, status, balance_bdt`

### GET /api/reports/export/investment-register/
Columns: `investment_id, title, investment_type, invested_to, invested_amount, return_amount, pnl_amount, created_date, close_date, status, member_count, created_by, fund_released_by`

### GET /api/reports/export/distribution-logs/
Columns: `distribution_id, investment_title, pnl_amount, rounded_total, remainder_applied, status, posted_by, posted_at, reversed_by, reversed_at`

### GET /api/reports/export/member-statement/{user_id}/
Member can export their own. Staff can export any member's.
Columns: `ledger_id, entry_type, amount, currency, txn_date, running_balance, reference_type, reference_id, comment, created_at`

---

## Full system endpoint map (all 5 phases)

```
AUTH
  POST   /api/auth/login/
  POST   /api/auth/logout/
  POST   /api/auth/token/refresh/
  POST   /api/auth/change-password/
  GET    /api/auth/me/
  PATCH  /api/auth/me/

USERS
  POST   /api/users/
  GET    /api/users/
  GET    /api/users/{user_id}/
  PATCH  /api/users/{user_id}/
  DELETE /api/users/{user_id}/

SUBMISSIONS
  POST   /api/submissions/
  GET    /api/submissions/
  GET    /api/submissions/{id}/
  POST   /api/submissions/{id}/attachments/
  GET    /api/submissions/queue/
  POST   /api/submissions/{id}/approve/
  POST   /api/submissions/{id}/reject/

LEDGER
  GET    /api/ledger/
  GET    /api/ledger/members/{user_id}/
  POST   /api/ledger/admin-post/

INVESTMENTS
  POST   /api/investments/
  GET    /api/investments/
  GET    /api/investments/{id}/
  PATCH  /api/investments/{id}/
  POST   /api/investments/{id}/release-funds/
  POST   /api/investments/{id}/close/
  GET    /api/investments/{id}/snapshot/
  POST   /api/investments/{id}/distribute/
  GET    /api/investments/{id}/distribution/
  POST   /api/investments/{id}/reverse/

REPORTS
  GET    /api/reports/my-statement/
  GET    /api/reports/my-distributions/
  GET    /api/reports/association-summary/
  GET    /api/reports/member-balances/
  GET    /api/reports/investment-register/
  GET    /api/reports/distribution-logs/
  GET    /api/reports/approval-queue-report/
  GET    /api/reports/export/member-balances/
  GET    /api/reports/export/investment-register/
  GET    /api/reports/export/distribution-logs/
  GET    /api/reports/export/member-statement/{user_id}/
```