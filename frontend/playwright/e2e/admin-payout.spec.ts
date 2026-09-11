import { test, expect } from '@playwright/test';

test('admin visits login', async ({ page }) => {
  await page.goto('http://localhost:5173/admin/login');
  await expect(page.getByRole('heading', { name: 'Admin Login' })).toBeVisible();
});
