import { test, expect, type Page } from '@playwright/test'

const ADMIN_EMAIL = 'admin@demo.local'
const ADMIN_PASSWORD = 'ChangeMe123!'

async function login(page: Page) {
  await page.goto('/login')
  const emailInput = page.locator('input[type="email"]')
  const passwordInput = page.locator('input[type="password"]')
  await emailInput.fill(ADMIN_EMAIL)
  await passwordInput.fill(ADMIN_PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/$/, { timeout: 15_000 })
}

test('login with correct credentials succeeds', async ({ page }) => {
  await page.goto('/login')
  await page.locator('input[type="email"]').fill(ADMIN_EMAIL)
  await page.locator('input[type="password"]').fill(ADMIN_PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/$/, { timeout: 15_000 })
})

test('login with wrong password shows error', async ({ page }) => {
  await page.goto('/login')
  await page.locator('input[type="email"]').fill(ADMIN_EMAIL)
  await page.locator('input[type="password"]').fill('WrongPassword123!')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.locator('text=Invalid email or password')).toBeVisible({ timeout: 15_000 })
  await expect(page).toHaveURL(/\/login/)
})

test('navigates to POS after login', async ({ page }) => {
  await login(page)
  await page.getByRole('link', { name: /POS|Register/i }).first().click()
  await expect(page).toHaveURL(/\/pos/, { timeout: 10_000 })
})