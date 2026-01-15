# API Endpoints Specification

## Overview
Restful API endpoints for the backend. All responses should return JSON.
Global prefix: `/api/v1`

## Error Handling
Standard error format:
```json
{
  "success": false,
  "error": "Error message description"
}
```

## Legacy/Success Format
Standard success format:
```json
{
  "success": true,
  "data": { ... }
}
```

## Endpoints

### 1. Authentication (`/auth`)
*   `POST /auth/signup`
    *   Body: `{ email, password, name? }`
    *   Response: `{ token, user: { id, email, role } }`
*   `POST /auth/login`
    *   Body: `{ email, password }`
    *   Response: `{ token, user }`
*   `GET /auth/me`
    *   Header: `Authorization: Bearer <token>`
    *   Response: `{ user }`

### 2. Menu (`/menu`)
*   `GET /menu`
    *   Public access. Returns list of available menu items.
    *   Response: `[ { id, name, price, ... }, ... ]`
*   `POST /menu` (Admin Only)
    *   Body: `{ name, price, category, ... }`
    *   Response: `{ id, ...createdItem }`
*   `PUT /menu/:id` (Admin Only)
    *   Body: `{ ...fields to update }`
*   `DELETE /menu/:id` (Admin Only)

### 3. Orders (`/orders`)
*   `POST /orders` (User)
    *   Body: `{ items: [ { menu_item_id, quantity }, ... ] }`
    *   Response: `{ id, status, total_amount }`
*   `GET /orders` (Admin: All orders, User: My orders)
    *   Response: `[ { id, status, total, items: [...] }, ... ]`
*   `PATCH /orders/:id/status` (Admin Only)
    *   Body: `{ status: 'PREPARING' }`

## TDD Instructions
**For every endpoint defined here, you MUST write an integration test using `supertest` BEFORE implementing the controller logic.**
1.  Write test case: "POST /auth/signup creates a user"
2.  Run test -> Fail (404/500)
3.  Implement Route/Controller
4.  Run test -> Pass
