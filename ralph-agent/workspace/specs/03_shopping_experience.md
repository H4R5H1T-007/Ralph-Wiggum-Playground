# Shopping Experience (Customer)

## Context
Customers browse the "Indian Aroma" menu to select items for order or wishlist.

## Requirements
1.  **Browse Menu**: Users see categories (Starters, Mains, etc.) and lists of items.
2.  **Wishlist**: Users can "heart" items to save them for later.
3.  **Cart**: Users can add items to a cart/order list.
4.  **Place Order (MVP)**:
    *   Users review their selected items.
    *   Users submit the order.
    *   System records the order and clears the cart.
    *   (No detailed payment gateway needed for MVP; assume "Cash on Delivery" or similar).

## Acceptance Criteria
- [ ] **Wishlist Toggle**: User clicks heart; item appears in "My Wishlist".
- [ ] **Add to Cart**: User adds 2 Naans; Cart shows 2 Naans and correct subtotal.
- [ ] **Place Order**: User submits order; sees "Order Placed" confirmation; Order appears in Admin panel.
- [ ] **Empty Cart**: Cannot place order with 0 items.

## Technical Acceptance Criteria
- [ ] **Type Safety**: Cart state and Order actions are strictly typed.
- [ ] **Unit Tests**: Cart arithmetic (subtotals, adding/removing items) is verified by tests.
- [ ] **Component Tests**: Wishlist toggle interaction is tested.
