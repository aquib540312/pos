# RBAC Frontend UI Gating

Implement complete frontend permission-based UI gating using the existing backend RBAC system.

## Goal

The backend RBAC is already implemented and endpoints are protected with `require_permission(Perm.X)`.

The frontend currently only checks whether the user is logged in. Fix this so the frontend uses the user's resolved permissions consistently.

## 1. Update `/auth/me`

Inspect the existing `/auth/me` response and auth schemas.

Add the user's resolved permissions to the response.

Example shape:

```json
{
  "id": "...",
  "name": "...",
  "email": "...",
  "role": "...",
  "permissions": [
    "products.view",
    "products.create",
    "products.edit"
  ]
}
```

Do not duplicate permission logic in the frontend. The backend remains the source of truth.

Use the existing permission enum/constants wherever possible.

## 2. Store permissions in frontend auth state

When `/auth/me` is loaded, store the permissions in the existing auth/user state.

Create a reusable permission helper/hook such as:

```ts
useCan("products.delete")
```

It should return a boolean.

Also support checking multiple permissions when useful, for example:

```ts
useCan("products.edit")
```

Keep the implementation simple and reusable.

## 3. Sidebar / Layout

Inspect `Layout.tsx`.

Currently all 19 menu items are rendered for every authenticated user.

Add the required permission to each menu item and filter the sidebar based on the logged-in user's permissions.

Examples:

- Products → `products.view`
- Purchasing → corresponding purchasing permission
- Sales → corresponding sales permission
- Reports → corresponding reports permission
- Staff → `staff.view`
- Audit Log → corresponding audit permission

Do NOT invent permission names blindly.

First inspect the existing backend `Perm` definitions and endpoint permissions, then map the frontend menu items to the actual existing permissions.

A user should not see a menu item when they do not have its required permission.

## 4. Route Protection

`ProtectedRoute` currently only verifies authentication.

Add permission-aware route protection.

For example:

```tsx
<ProtectedRoute permission="staff.view">
   <StaffPage />
</ProtectedRoute>
```

If a user manually enters a URL for a page they do not have permission for:

- Do not render the page.
- Do not merely wait for the backend 403.
- Show a proper "Access denied" page/message or redirect to an allowed page.

Do not break the existing authentication protection.

## 5. Feature-Level Permissions

Do not stop at sidebar and routes.

Inspect important pages and hide/disable actions based on permissions.

Examples:

```tsx
{can("products.create") && <Button>Add Product</Button>}
```

```tsx
{can("products.delete") && <Button>Delete</Button>}
```

```tsx
{can("sales.close_shift") && <Button>Close Shift</Button>}
```

Apply this to existing permission-protected functionality such as:

- Create
- Edit
- Delete
- Approve
- Cancel
- Close shift
- Manage users/staff
- Reports
- Audit log
- Purchasing actions
- Sales actions
- Inventory actions

Use the actual permission names already defined by the backend.

Do not create fake permissions just to make the UI work.

## 6. Security Rule

Frontend permission checks are UX protection, NOT security.

Keep all existing backend `require_permission(...)` checks intact.

Never remove backend authorization because the frontend now hides buttons/routes.

The backend must remain capable of returning 403 for unauthorized API calls.

## 7. Handle Loading State

Avoid briefly showing all menus/buttons before `/auth/me` finishes loading.

The permission-aware UI should have a proper loading state so a restricted user does not see unauthorized navigation momentarily.

## 8. Super Admin / Full Permission Role

Inspect how the existing backend represents admin/super-admin/full-access roles.

Do not hardcode assumptions unless the backend already has such behavior.

Ensure the highest-privilege role continues to see/access everything it currently can.

## 9. Tests

Add or update tests for:

### Sidebar

- User with permission sees menu item.
- User without permission does not see menu item.

### Routes

- Authorized user can access route.
- Unauthorized user receives access-denied behavior.

### Actions

- User with `products.delete` sees Delete.
- User without `products.delete` does not see Delete.

### Backend

Confirm existing backend authorization tests still pass.

## 10. Regression Check

After implementation:

1. Run backend tests.
2. Run frontend tests.
3. Run TypeScript/type checking.
4. Build the frontend.
5. Start the application if practical.
6. Test at least two different roles manually.
7. Verify direct URL access for restricted pages.
8. Verify API 403 behavior remains intact.

## Important

Before modifying anything, inspect:

- `Perm` definitions
- `/auth/me`
- auth schemas
- auth store/context
- `Layout.tsx`
- `ProtectedRoute`
- routing configuration
- existing permission checks
- Staff/role implementation
- representative CRUD pages

Then implement the smallest clean architecture that works with the existing codebase.

Do not rewrite unrelated parts of the application.

At the end, report:

1. Files changed
2. Permission mapping created
3. Components/hooks added
4. Tests run and results
5. Any permission names that were ambiguous or missing
6. Any remaining frontend pages that still need feature-level gating