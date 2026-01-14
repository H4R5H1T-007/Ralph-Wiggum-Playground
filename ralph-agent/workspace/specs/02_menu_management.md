# Menu Management (Admin)

## Context
The Admin needs full control over the "Indian Aroma" menu to manage daily offerings, prices, and availability.

## Requirements
1.  **Create Item**: Admin can add new food items (Name, Description, Price, Image, Category).
2.  **Edit Item**: Admin can update details of existing items.
3.  **Manage Availability**: Admin can mark items as "Available" or "Sold Out".
    *   "Sold Out" items should be visible but not orderable by customers.
4.  **Price Control**: Admin can adjust pricing instantly.

## Acceptance Criteria
- [ ] **Add Item**: Admin adds "Chicken Tikka"; it appears immediately on the main menu.
- [ ] **Update Price**: Admin changes price from $10 to $12; change is reflected.
- [ ] **Sold Out**: Admin marks "Samosa" as Sold Out; 'Add' button is disabled for users.
- [ ] **Validation**: Price cannot be negative; Name is required.

## Technical Acceptance Criteria
- [ ] **Type Safety**: Menu items use a strict TypeScript interface `MenuItem`.
- [ ] **Unit Tests**: CRUD operations for menu items have passing tests.
- [ ] **Edge Cases**: Tests cover negative prices and empty strings.
