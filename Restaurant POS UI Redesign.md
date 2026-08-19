Redesign the existing `/restaurant` screen into a **production-quality Restaurant POS UI**.

IMPORTANT:
- First inspect the existing Restaurant POS implementation, components, API calls, types, CSS, routing and current tests.
- **Do NOT rewrite or break the existing backend/business logic.**
- Reuse existing APIs and functionality wherever possible.
- Do not create fake/mock data.
- Do not remove currently working features.
- Preserve existing RBAC: `DINING_MANAGE` and related permissions.
- Before changing anything, understand the current implementation and existing UI patterns.

## Goal

The screen should feel like a **real restaurant cashier/waiter POS**, not an admin dashboard.

Optimize for:
- Fast ordering
- Minimum clicks
- Large touch-friendly controls
- Clear table status
- Quick menu search
- Persistent current order
- Fast KOT sending
- Fast settlement/payment
- Clear visual feedback

## Layout

Create a responsive 3-panel POS layout.

### 1. LEFT — Tables

Show restaurant tables as cards.

Each card should show:
- Table number/name
- Status
- Current order amount if occupied
- Order elapsed time if applicable

Statuses:
- Available
- Occupied
- Reserved
- Cleaning

Add area/floor filtering if the existing data model supports it.

Example:

T01
Available

T02
Occupied
₹420
32 min

T03
Reserved

Use clear status styling but keep the UI professional and accessible.

Clicking an occupied table should load its active order.

Clicking an available table should allow starting a new order.

## 2. CENTER — Menu

Top:
- Menu search
- Category filters
- Optional quick filters such as Popular / All

Menu items should be displayed as large POS-friendly cards.

Each card:
- Item name
- Price
- Availability
- Add button

Clicking an item should add it quickly to the current order.

If the existing backend supports modifiers/options, provide a compact modifier popup instead of a large form.

Modifier popup should support where applicable:
- Quantity
- Options
- Notes
- Add to order

Avoid unnecessary navigation.

## 3. RIGHT — Current Order

Keep this panel persistent.

Header:
- Table
- Order number
- Waiter/user if available
- Order status

Order items:

Chicken Biryani
2 × ₹25 = ₹50

Chicken 65
1 × ₹18 = ₹18

Each item should allow:
- Increase quantity
- Decrease quantity
- Remove
- Edit notes/modifiers if supported

Bottom:

Subtotal
Tax
Discount
Total

Primary actions:

[SAVE / HOLD]

[SEND KOT]

[SETTLE PAYMENT]

Make `SEND KOT` and `SETTLE PAYMENT` visually prominent.

## KOT workflow

Use the existing KOT API/functionality.

After sending KOT:
- Show confirmation
- Display KOT number
- Update order/KOT status
- Provide reprint if supported
- Prevent accidental duplicate KOT submission

Do not fake KOT data.

If the existing system already supports 72mm KOT printing, preserve that functionality.

## Settlement UI

Create a fast payment modal/screen.

Display:

TOTAL
₹87

Payment methods:
- Cash
- Card
- Other existing supported methods

If the backend already supports multiple/partial payments, expose them properly.

For cash:
- Amount received
- Change

Primary action:

[COMPLETE PAYMENT]

After successful settlement:
1. Existing settlement API executes
2. Existing invoice generation executes
3. Show invoice number
4. Table becomes available
5. Refresh table/order state

Handle API failure safely.

Do NOT mark the table as available locally if settlement/invoice operation actually failed.

## UX requirements

The POS should minimize typing.

Add:
- Fast search
- Keyboard-friendly navigation where practical
- Large clickable targets
- Sticky current-order panel
- Clear loading states
- Empty states
- Error states
- Success notifications
- Confirmation only for destructive actions
- Disable buttons during API requests to prevent duplicate submissions

Avoid:
- Huge forms
- Excessive modals
- Admin-style dense tables
- Unnecessary page navigation
- Fake functionality
- Hardcoded business data

## Responsive behavior

Desktop:
3-panel POS layout.

Tablet:
2-panel layout with order drawer/panel.

Small screen:
tables/menu and order should remain usable without creating a broken desktop layout.

## Visual design

Make it modern and professional.

Use the existing application's design system, typography, spacing and components where possible.

The UI should look suitable for:
- Restaurant cashier
- Waiter tablet
- Small restaurant POS terminal

Prioritize usability over decorative design.

## Existing functionality that MUST continue working

Verify all existing functionality after the redesign:

- Table creation/display
- Table status
- Open order
- Add items
- Quantity changes
- Estimate
- KOT
- Kitchen send
- Serve
- Settlement
- Invoice
- Cancel
- KOT printing
- Permissions/RBAC
- Existing routes

Do not regress existing backend functionality.

## Testing

Before finishing:

1. Run existing backend tests.
2. Run existing frontend tests.
3. Run existing Playwright/E2E tests.
4. Add/update E2E tests for the new POS workflow.

At minimum verify:

Login
→ Restaurant
→ Select available table
→ Add menu item
→ Change quantity
→ Send KOT
→ Serve
→ Settle
→ Invoice generated
→ Table becomes available

Also test:
- occupied table
- empty order
- duplicate clicks
- API loading/error state
- permission restriction

Run build and lint.

## Final response

When finished, report:

- Files changed
- UI components created/modified
- Existing APIs reused
- Tests added/changed
- Test results
- Build result
- Lint result
- Any remaining UX or technical issues

Do not stop at making it visually attractive. The final result must be a **usable restaurant POS workflow connected to the existing real backend**.