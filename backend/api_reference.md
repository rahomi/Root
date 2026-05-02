# PHASE 1: # Auth API Reference

Base URL: `/api/`
All protected endpoints require: `Authorization: Bearer <access_token>`

---

## POST /api/auth/login/
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

## POST /api/auth/token/refresh/
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

## POST /api/auth/logout/
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

## POST /api/auth/change-password/
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

## GET /api/auth/me/
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

## POST /api/users/
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

## GET /api/users/
**Requires: MANAGE_USERS**

Query params:
- `status=ACTIVE|INACTIVE`
- `role=SUPER_ADMIN|ADMIN|MEMBER`
- `search=<name substring>`

Response `200`: Array of user objects

---

## GET /api/users/{user_id}/
**Self or MANAGE_USERS**

Response `200`: Full user object

---

## PATCH /api/users/{user_id}/
**Self** → can update: full_name, email, contact_no, notes
**MANAGE_USERS** → can also update: role, status, join_date

---

## DELETE /api/users/{user_id}/
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


# PHASE 2 — API Reference Submisssions and Ledgers

Base URL: `/api/`
All endpoints require: `Authorization: Bearer <access_token>`

---

## Submissions

### POST /api/submission/
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

### GET /api/submission/
Member's own submission. Query params: `?status=PENDING|APPROVED|REJECTED`

Response `200`: Array of submission objects

---

### GET /api/submission/{request_id}/
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

### GET /api/submission/queue/
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

### POST /api/submission/{request_id}/approve/
Approve a PENDING request. Requires `APPROVE_SUBMISSION`.
Body: `{}` (empty)

Response `200`: Updated submission object with `status: "APPROVED"` and `resulting_ledger_id` set.

---

### POST /api/submission/{request_id}/reject/
Reject a PENDING request. Requires `APPROVE_SUBMISSION`.

Request:
```json
{ "rejection_reason": "Payment reference could not be verified." }
```

Response `200`: Updated submission with `status: "REJECTED"`

---

## Ledger

### GET /api/ledger/
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

### GET /api/ledger/members/{user_id}/
Any member's ledger. Requires `VIEW_ALL_REPORTS`.
Same response shape as above, plus user info at the top.

---

### POST /api/ledger/admin-post/
Admin-direct ledger entry. Requires `POST_ADMIN_LEDGER`.

Request:
```json
{
  "user_id":      "uuid",
  "entry_type":   "ADJUSTMENT",
  "amount":       "-500.00",
  "txn_date":     "2024-06-20",
  "comment":      "Correction for duplicate entry",
  "reference_id": ""
}
```
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