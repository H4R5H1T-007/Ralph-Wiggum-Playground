# Order Management (Admin)

## Context
The Admin acts as the central hub for processing orders.

## Requirements
1.  **Order Dashboard**: Admin sees a list of all active orders.
2.  **Status Workflow**:
    *   Orders start as "Pending".
    *   Admin can move them to "Accepted", "Preparing", "Ready", "Delivered".
3.  **Modify Order**:
    *   Admin can edit an order (e.g., if a customer calls to change quantity or remove an item).
    *   Total price recalculates automatically.

## Acceptance Criteria
- [ ] **View Orders**: New customer order appears at the top of the list.
- [ ] **Update Status**: Admin changes status to "Ready"; status updates in DB.
- [ ] **Edit Order**: Admin removes an item from Order #123; total drops accordingly.
- [ ] **Order History**: Delivered orders are accessible in history.

## Technical Acceptance Criteria
- [ ] **Type Safety**: Order Status transitions use a TypeScript Enum/Union type.
- [ ] **Unit Tests**: Status update logic and total recalculation (on edit) are covered by tests.
- [ ] **Data Integrity**: Tests ensure orders cannot be lost during status updates.
