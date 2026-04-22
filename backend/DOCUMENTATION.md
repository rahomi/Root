# Root Backend

Backend service for the Root association management app. The current implementation is a Django project scaffold with a custom user model, a fine-grained permission system, and PostgreSQL-based configuration.

## Current Status

This backend is in early scaffold stage.

Implemented so far:

- Django project bootstrap under `rootBackend/`
- Custom auth user model in `accounts`
- Fine-grained permission catalog and per-user grants in `permissions`
- Custom Django auth backend that routes permission checks through the project permission tables
- View decorator for permission-protected endpoints
- PostgreSQL environment-based database configuration

Not implemented yet:

- Business domain apps for members, submissions, ledger, investments, reports, and audit logs
- API endpoints beyond the default Django admin route
- Serializers, services, and application-layer business logic
- Initial data migrations for permission seeding
- Pinned dependency manifest such as `requirements.txt`

## Project Structure

```text
backend/
├── manage.py
├── .env.example
├── README.md
├── rootBackend/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── accounts/
│   ├── apps.py
│   ├── admin.py
│   ├── backends.py
│   ├── models.py
│   ├── tests.py
│   └── views.py
└── permissions/
    ├── apps.py
    ├── admin.py
    ├── decorators.py
    ├── models.py
    ├── tests.py
    └── views.py
```

## Technology Choices

The current codebase is built around:

- Django for the core backend framework
- PostgreSQL as the configured database backend
- Django REST Framework and Simple JWT as installed application dependencies in settings
- `python-dotenv` for loading environment variables from `.env`

Only Django admin is wired into the URL configuration at this stage.

## Configuration

Core configuration lives in `rootBackend/settings.py`.

Important settings already in place:

- `INSTALLED_APPS` includes `accounts` and `permissions`
- `AUTH_USER_MODEL = 'accounts.User'` enables the custom user model
- `AUTHENTICATION_BACKENDS = ['accounts.backends.RootPermissionBackend']` enables custom permission resolution
- `DATABASES['default']` is configured for PostgreSQL using environment variables

Environment variables expected by the project are documented in `.env.example`:

- `SECRET_KEY`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`

## Accounts App

The `accounts` app defines the system user model and authentication behavior.

### User Model

`accounts.models.User` is a custom Django user model built on `AbstractBaseUser` and `PermissionsMixin`.

Key fields:

- `user_id`: UUID primary key
- `full_name`: display name of the user
- `contact_no`: unique login identifier and username field
- `email`: optional unique email address
- `join_date`: date the user joined the association
- `role`: high-level classification such as `SUPER_ADMIN`, `ADMIN`, or `MEMBER`
- `status`: business status such as `ACTIVE` or `INACTIVE`
- `notes`: free-text notes
- `is_staff`: Django admin access flag
- `is_active`: Django authentication activation flag
- `created_at` and `updated_at`: audit timestamps

Authentication details:

- `USERNAME_FIELD = 'contact_no'`
- `REQUIRED_FIELDS = ['full_name', 'join_date']`

### User Manager

`UserManager` provides:

- `create_user()` for standard user creation
- `create_superuser()` for admin creation with the expected Django flags

### Permission Check Method

`User.has_permission(code)` is the project-level helper used for fine-grained authorization.

It returns `True` only when the user has a matching permission grant that is:

- linked to the user
- active
- not expired, or has no expiry date

This method is the core lookup used by both the custom auth backend and the permission decorator.

## Permissions App

The `permissions` app implements a fine-grained access control model.

### PermissionCode

`PermissionCode` is a `TextChoices` enum containing the valid permission identifiers used throughout the system.

Current codes include:

- `APPROVE_SUBMISSION`
- `POST_ADMIN_LEDGER`
- `CREATE_INVESTMENT`
- `RELEASE_INVESTMENT_FUNDS`
- `CLOSE_INVESTMENT`
- `DISTRIBUTE_PL`
- `REVERSE_DISTRIBUTION`
- `VIEW_ALL_REPORTS`
- `MANAGE_USERS`

### Permission Model

`permissions.models.Permission` is the master permission catalog.

Purpose:

- stores one row per supported permission
- ensures permission codes remain standardized
- supports human-readable descriptions for admin or documentation use

Fields:

- `permission_id`: UUID primary key
- `code`: unique permission code from `PermissionCode`
- `description`: human-readable explanation

### UserPermission Model

`permissions.models.UserPermission` is the join model between users and permissions.

Purpose:

- grants a specific permission to a specific user
- records who granted the permission
- supports expiry-based access
- supports soft revocation without deleting history

Fields:

- `user_permission_id`: UUID primary key
- `user`: the user receiving the permission
- `permission`: the granted permission
- `granted_by`: user who issued the grant
- `granted_at`: timestamp of grant creation
- `expires_at`: optional permission expiry timestamp
- `is_active`: active flag for soft revoke
- `revoked_by`: user who revoked the permission
- `revoked_at`: timestamp of revocation

Constraints and indexes:

- unique per `(user, permission)` so duplicate grants are not allowed
- indexed by `(user, is_active)` for faster active-permission lookups

## Model Relationship

The fine-grained authorization model is centered around three classes:

- `accounts.User`
- `permissions.Permission`
- `permissions.UserPermission`

Relationship summary:

- one user can have many permission grants
- one permission can be granted to many users
- `UserPermission` is the bridge table that connects them

Conceptually:

```text
User -> UserPermission -> Permission
```

This means the system does not decide capabilities directly from `role`. Instead, `role` is a coarse classification and actual capabilities are granted through `UserPermission`.

## Authentication and Authorization Flow

### Login Flow

Authentication uses Django’s standard backend flow with the project user model:

1. Django authenticates a user against `accounts.User`
2. The login identifier is `contact_no`
3. Password hashing and verification are handled by Django through `AbstractBaseUser`

### Permission Resolution Flow

Custom permission checks are handled by `accounts.backends.RootPermissionBackend`.

Flow:

1. Application code calls `user.has_perm('permissions.MANAGE_USERS')` or similar
2. Django routes the check to `RootPermissionBackend.has_perm()`
3. The backend rejects anonymous or inactive users
4. The backend allows Django superusers immediately
5. The backend extracts the final permission code from the string
6. The backend calls `user.has_permission(code)`
7. `User.has_permission()` queries `UserPermission` for an active, non-expired grant
8. The method returns `True` if such a grant exists, otherwise `False`

### Decorator-Based Protection

`permissions.decorators.require_permission(code)` provides a view-level access decorator.

Flow:

1. If the request user is not authenticated, the decorator redirects to login
2. If the user lacks the required permission, it raises `PermissionDenied`
3. If the user has the permission, the wrapped view executes normally

This decorator is intended for function-based views and provides a straightforward way to enforce project permissions.

## Current URL Surface

`rootBackend/urls.py` currently exposes only:

- `/admin/`

No API routes or app-specific URLs are connected yet.

## Local Setup

Because the repository does not yet include a pinned dependency file, setup is currently manual.

Suggested local workflow:

1. Create and activate a Python virtual environment
2. Install Django and the supporting packages used by the project
3. Create a `.env` file based on `.env.example`
4. Provision a PostgreSQL database
5. Run migrations
6. Create a superuser
7. Start the development server

Typical commands:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Run all commands from the `backend/` directory.

## Known Gaps and Follow-Up Work

The backend still needs the following before it can support the full product scope:

- add migration files for `accounts` and `permissions`
- seed the `Permission` table through a data migration or management command
- register the models in Django admin
- define API routes, serializers, and views
- add tests for authentication, permission checks, and model constraints
- document and pin dependencies in a `requirements.txt` or `pyproject.toml`
- add JWT authentication configuration if token-based APIs are planned

## Development Notes

The current backend design uses permission grants instead of relying only on role checks.

This is important because:

- users with the same role can still have different capabilities
- access can be granted temporarily through `expires_at`
- access can be revoked without deleting the record
- permission history remains more auditable than simple boolean flags

When adding new protected operations, prefer checking fine-grained permission codes rather than branching directly on `role`.
