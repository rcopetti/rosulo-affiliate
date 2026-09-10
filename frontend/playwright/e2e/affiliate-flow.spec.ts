import { test, expect } from '@playwright/test';

test('affiliate visits login', async ({ page }) => {
  await page.goto('http://localhost:5173/login');
  await expect(page.getByRole('heading', { name: 'Affiliate Login' })).toBeVisible();
});
