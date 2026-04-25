# Auth API Reference

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