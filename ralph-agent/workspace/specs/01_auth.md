# Authentication & Roles

## Context
The system requires two types of users: Customers (who order food) and the Admin (the home kitchen owner).

## Requirements
1.  **Customer Registration/Login**:
    *   Users can sign up with Email/Password.
    *   Users can log in to access their profile and history.
2.  **Admin Access**:
    *   A specific secure login for the Admin.
    *   Access to the Admin Dashboard is strictly protected.

## Acceptance Criteria
- [ ] **Customer Signup**: A new user can register and is logged in immediately.
- [ ] **Customer Login**: Existing user can log in with correct credentials; incorrect credentials show error.
- [ ] **Admin Recognition**: System identifies the Admin user (hardcoded or role-based) and grants access to `/admin`.
- [ ] **Protection**: Non-admin users attempting to access `/admin` are redirected to home.

## Technical Acceptance Criteria
- [ ] **Type Safety**: All Auth functions/components are strictly typed.
- [ ] **Unit Tests**: Login validation and redirection logic is covered by passing unit tests.
- [ ] **Security**: Passwords are NOT stored in plain text (even for MVP).
