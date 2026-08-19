import { test, expect } from '@playwright/test'

test('inspect purchasing page', async ({ page }) => {
  await page.goto('/login')
  await page.locator('input[type="email"]').fill('admin@demo.local')
  await page.locator('input[type="password"]').fill('ChangeMe123!')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/$/, { timeout: 15_000 })

  await page.goto('/purchasing')
  await expect(page.getByRole('heading', { name: 'Purchasing' })).toBeVisible({ timeout: 15_000 })

  const tabs = await page.locator('button', { hasText: /Purchase Orders|Goods Receipts|Returns/ }).allTextContents()
  console.log('TABS:', tabs)

  await page.getByRole('button', { name: 'Goods Receipts' }).click()
  const recvBtn = page.getByRole('button', { name: '+ Receive Stock' })
  console.log('RECEIVE STOCK BUTTON COUNT:', await recvBtn.count())
  await recvBtn.click()
  await expect(page.getByPlaceholder('Search product to add...')).toBeVisible({ timeout: 10_000 })
  console.log('RECEIVE FORM OK - can add products')
  console.log('SELECT OPTIONS:', await page.locator('select').first().locator('option').allTextContents())
})