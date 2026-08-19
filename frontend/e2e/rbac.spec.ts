import { test, expect, type Page, type APIRequestContext } from '@playwright/test'

const ADMIN_EMAIL = 'admin@demo.local'
const ADMIN_PASSWORD = 'ChangeMe123!'

const CASHIER_EMAIL = 'cashier-e2e@example.com'
const CASHIER_PASSWORD = 'ChangeMe123!'

async function login(page: Page, email: string, password: string) {
  await page.goto('/login')
  await page.locator('input[type="email"]').fill(email)
  await page.locator('input[type="password"]').fill(password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.getByRole('link', { name: 'Billing (POS)' }).first().waitFor({ timeout: 15_000 })
}

async function adminToken(request: APIRequestContext): Promise<string> {
  const form = new URLSearchParams()
  form.set('username', ADMIN_EMAIL)
  form.set('password', ADMIN_PASSWORD)
  const resp = await request.post('/api/v1/auth/login', {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    data: form.toString(),
  })
  expect(resp.status()).toBe(200)
  return (await resp.json()).access_token as string
}

async function ensureCashier(request: APIRequestContext, dbToken: string): Promise<string> {
  const auth = { Authorization: `Bearer ${dbToken}` }
  const roles = await request.get('/api/v1/rbac/roles', { headers: auth })
  expect(roles.status()).toBe(200)
  const rows = (await roles.json()) as { id: string; name: string }[]
  const cashierRole = rows.find((r) => r.name === 'cashier')
  if (!cashierRole) throw new Error('cashier role not seeded')

  const existing = await request.get('/api/v1/auth/users', { headers: auth })
  const users = (await existing.json()) as { id: string; email: string }[]
  const found = users.find((u) => u.email === CASHIER_EMAIL)
  if (found) {
    // Re-activate: a previous run deactivates the cashier in its finally block,
    // so the user may still exist (inactive) on the next run.
    await request.patch(`/api/v1/auth/users/${found.id}/active`, {
      headers: auth,
      data: { is_active: true },
    })
    return found.id
  }

  const created = await request.post('/api/v1/auth/users', {
    headers: auth,
    data: {
      full_name: 'Cashier E2E',
      email: CASHIER_EMAIL,
      password: CASHIER_PASSWORD,
      role_ids: [cashierRole.id],
    },
  })
  expect(created.status()).toBe(201)
  return (await created.json()).id as string
}

test('admin sees admin-only nav items and can open staff page', async ({ page }) => {
  await login(page, ADMIN_EMAIL, ADMIN_PASSWORD)
  await expect(page.getByRole('link', { name: 'Staff' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Reports' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Audit Log' })).toBeVisible()

  await page.goto('/staff')
  await expect(page.getByRole('heading', { name: /Staff/i })).toBeVisible({ timeout: 10_000 })
})

test('cashier nav is filtered and direct access to staff page is denied', async ({
  page,
  request,
}) => {
  const dbToken = await adminToken(request)
  const cashierId = await ensureCashier(request, dbToken)

  try {
    await login(page, CASHIER_EMAIL, CASHIER_PASSWORD)
    // Allowed: POS billing is a cashier's primary page (also the landing page).
    await expect(page.getByRole('link', { name: 'Billing (POS)' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Shift & Cash' })).toBeVisible()

    // Denied: these menus must not be rendered without the permission.
    await expect(page.getByRole('link', { name: 'Staff' })).toHaveCount(0)
    await expect(page.getByRole('link', { name: 'Reports' })).toHaveCount(0)
    await expect(page.getByRole('link', { name: 'Audit Log' })).toHaveCount(0)
    await expect(page.getByRole('link', { name: 'Purchasing' })).toHaveCount(0)

    // Direct URL access is blocked with an access-denied message, not a 403 page.
    await page.goto('/staff')
    await expect(page.getByRole('heading', { name: 'Access denied' })).toBeVisible({ timeout: 10_000 })
  } finally {
    const auth = { Authorization: `Bearer ${dbToken}` }
    await request.patch(`/api/v1/auth/users/${cashierId}/active`, {
      headers: auth,
      data: { is_active: false },
    })
  }
})