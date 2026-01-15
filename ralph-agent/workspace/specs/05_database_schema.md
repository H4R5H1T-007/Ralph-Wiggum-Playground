# Database Schema (SQLite)

## Overview
This document defines the database schema for the Indian Aroma application. The database is **SQLite**.
All tables must include `created_at` and `updated_at` timestamps.

## Tables

### 1. `User`
Stores customer and admin information.
*   `id` (Integer, Primary Key, Auto Increment)
*   `email` (String, Unique, Not Null)
*   `password_hash` (String, Not Null)
*   `role` (String, Default 'CUSTOMER', Enum: 'CUSTOMER', 'ADMIN')
*   `name` (String, Optional)
*   `created_at` (DateTime, Default Now)
*   `updated_at` (DateTime, Default Now)

### 2. `MenuItem`
Stores food menu items managed by the Admin.
*   `id` (Integer, Primary Key, Auto Increment)
*   `name` (String, Not Null)
*   `description` (String, Optional)
*   `price` (Decimal/Float, Not Null)
*   `category` (String, Not Null)
*   `image_url` (String, Optional)
*   `is_available` (Boolean, Default True)
*   `created_at` (DateTime, Default Now)
*   `updated_at` (DateTime, Default Now)

### 3. `Order`
Stores customer orders.
*   `id` (Integer, Primary Key, Auto Increment)
*   `user_id` (Integer, Foreign Key -> User.id, Nullable if guest checkout allowed, else Not Null)
*   `status` (String, Default 'PENDING', Enum: 'PENDING', 'PREPARING', 'READY', 'DELIVERED', 'CANCELLED')
*   `total_amount` (Decimal/Float, Not Null)
*   `created_at` (DateTime, Default Now)
*   `updated_at` (DateTime, Default Now)

### 4. `OrderItem`
Stores individual items within an order.
*   `id` (Integer, Primary Key, Auto Increment)
*   `order_id` (Integer, Foreign Key -> Order.id)
*   `menu_item_id` (Integer, Foreign Key -> MenuItem.id)
*   `quantity` (Integer, Not Null)
*   `price_at_time` (Decimal/Float, Not Null)  // Snapshot of price when ordered
