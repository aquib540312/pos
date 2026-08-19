import { test, expect } from '@playwright/test'

async function login(page: import('@playwright/test').Page) {
  await page.goto('/login')
  await page.locator('input[type="email"]').fill('admin@demo.local')
  await page.locator('input[type="password"]').fill('ChangeMe123!')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/$/, { timeout: 15_000 })
  await page.goto('/restaurant')
}

test('inspect restaurant page', async ({ page }) => {
  await login(page)
  await expect(page.getByRole('heading', { name: 'Restaurant' })).toBeVisible({ timeout: 15_000 })

  // Table cards load async after the branch fetch; wait for at least one.
  await expect(page.locator('button', { hasText: 'seats' }).first()).toBeVisible({ timeout: 15_000 })
  const tableBtns = page.locator('button', { hasText: /seats/ })
  console.log('TABLE CARDS:', await tableBtns.count())

  // Menu search + category chips should exist.
  await expect(page.getByPlaceholder('Search menu by name, SKU or barcode…')).toBeVisible()
  await expect(page.getByRole('button', { name: 'All' }).first()).toBeVisible()

  // Add a table via the header action.
  await page.getByRole('button', { name: '+ Add table' }).click()
  await expect(page.getByPlaceholder('T10')).toBeVisible({ timeout: 10_000 })
  console.log('ADD TABLE FORM OK')
})

test('POS flow: order → qty → KOT → serve → settle → invoice → table available', async ({ page }) => {
  await login(page)

  const tableNumber = `E2E-${Date.now().toString().slice(-5)}`

  // Create a fresh available table (deterministic, independent of existing data).
  await page.getByRole('button', { name: '+ Add table' }).click()
  await page.getByPlaceholder('T10').fill(tableNumber)
  await page.getByRole('button', { name: 'Save table' }).click()
  const tableCard = page.locator('button', { hasText: tableNumber })
  await expect(tableCard).toBeVisible({ timeout: 15_000 })
  await expect(tableCard.locator('span', { hasText: 'Available' })).toBeVisible()

  // Select the table and open an order.
  await tableCard.click()
  await page.getByRole('button', { name: 'Open table & start order' }).first().click()

  // Add the first menu item that has a configured GST rate (White Bread).
  const addBtn = page.locator('button[title="Add White Bread 400g"]').first()
  await expect(addBtn).toBeEnabled({ timeout: 15_000 })
  await addBtn.click()
  const kotBtn = page.getByRole('button', { name: /SEND KOT · 1 pending/ })
  await expect(kotBtn).toBeVisible({ timeout: 15_000 })

  // Increase quantity to 2 (KOT pending count is by item row, so stays 1).
  await page.getByRole('button', { name: '+', exact: true }).click()
  await expect(page.getByRole('spinbutton').first()).toHaveValue('2', { timeout: 15_000 })

  // Send KOT while disabled against double-submit.
  await page.getByRole('button', { name: /SEND KOT · 1 pending/ }).click()
  await expect(page.getByText('KITCHEN ORDER', { exact: false }).first()).toBeVisible({ timeout: 15_000 })
  await page.getByRole('button', { name: 'Close' }).first().click()

  // Kitchen status now preparing → mark served.
  await expect(page.getByRole('button', { name: /Mark 1 preparing served/ })).toBeVisible({ timeout: 15_000 })
  await page.getByRole('button', { name: /Mark 1 preparing served/ }).click()

  // Settle the bill.
  const settleBtn = page.getByRole('button', { name: /^SETTLE · / })
  await expect(settleBtn).toBeEnabled({ timeout: 15_000 })
  await settleBtn.click()
  await expect(page.getByRole('heading', { name: 'Settle bill' })).toBeVisible()

  // Amount is pre-filled to the grand total → complete payment.
  const completeBtn = page.getByRole('button', { name: 'COMPLETE PAYMENT' })
  await expect(completeBtn).toBeEnabled({ timeout: 10_000 })
  await completeBtn.click()

  // Invoice generated, order reset → the table is available again.
  await expect(page.getByText(/Invoice INV\//)).toBeVisible({ timeout: 20_000 })
  await expect(tableCard.locator('span', { hasText: 'Available' })).toBeVisible({ timeout: 15_000 })
})