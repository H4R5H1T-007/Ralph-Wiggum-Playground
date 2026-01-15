# Frontend UI Specification

## Overview
Next.js Application using TypeScript.
**CRITICAL REQUIREMENT**: Must implement a "Premium" aesthetic with dynamic interactions.
- Use **Framer Motion** for page transitions and element entry animations.
- Use **Skeleton Loaders** instead of spinners for data fetching.
- Use **Hot Toast** (or similar) for success/error notifications.
- **Glassmorphism** and subtle gradients are encouraged over flat colors.

## Core Pages

### 1. Home / Landing (`/`)
*   **Hero Section**: Attractive food imagery with **Parallax effect** or slow zoom animation. "Order Now" CTA with hover lift effect.
*   **Featured Items**: Display top 3 items in a carousel or animated grid.
*   **Footer**: Contact info, social links.

### 2. Menu Page (`/menu`)
*   **Categories Filter**: Tabs to switch categories (must animate indicator line).
*   **Menu Grid**: Responsive grid of `MenuCard` components (staggered fade-in entry).
*   **Cart Floating Action Button / Drawer Trigger**: Visible on mobile.

### 3. Auth Pages
*   `/login`: Email/Password form. Link to Signup.
*   `/signup`: Registration form.

### 4. Admin Dashboard (`/admin`)
*   **Protected Route**: Redirects if not admin.
*   **Tabs**: "Orders", "Menu Management".
*   **Orders View**: Live list of orders with Status toggles.
*   **Menu Management View**: Table to Edit/Delete items, "Add Item" button.

## Key Components

### `MenuCard`
*   Displays: Image, Name, Description, Price.
*   Action: "Add to Cart" button (Changes to +/- quantity if already in cart).

### `CartDrawer` (or Modal)
*   Lists selected items.
*   Shows subtotal/total.
*   "Checkout" button.

### `Navbar`
*   Logo (Indian Aroma).
*   Links: Home, Menu, Admin (if logged in).
*   User Profile / Logout.
*   Cart Icon (with badge count).

## State Management
*   **CartContext**: Global state for managing cart items.
    *   `addToCart(item)` -> Triggers a "Fly to cart" animation or distinct toast.
    *   `removeFromCart(itemId)`
    *   `clearCart()`
*   **AuthContext**: Global state for user session.

## UX Standards
1.  **Feedback**: Every button click must have a visual feedback (ripple, scale down).
2.  **Empty States**: Beautiful illustrations for empty cart or no search results.
3.  **Transitions**: Pages should cross-fade or slide; no hard jumps.

## Testing (Frontend TDD)
*   Use `React Testing Library`.
*   **Test 1**: `MenuCard` renders correct props.
*   **Test 2**: Clicking "Add to Cart" updates the `CartContext` (mocked).
*   **Test 3**: Admin page redirects unauthenticated users.
