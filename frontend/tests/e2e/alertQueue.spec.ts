import { test, expect } from '@playwright/test';

test.describe('Alert Queue', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should display mock alerts in the table', async ({ page }) => {
    // Check header
    await expect(page.locator('h1')).toContainText('Alert Queue');
    
    // Check if the mock alerts are loaded (T1110, T1059, T1190 are the mock techniques)
    await expect(page.getByText('T1110')).toBeVisible();
    await expect(page.getByText('T1059')).toBeVisible();
    await expect(page.getByText('T1190')).toBeVisible();
    
    // Check if the Triage buttons are present
    const triageButtons = page.getByRole('link', { name: 'Triage' });
    await expect(triageButtons).toHaveCount(3);
  });

  test('should filter alerts by search term', async ({ page }) => {
    // Search for T1110
    const searchInput = page.getByPlaceholder('Filter by IP, Host, User, or Technique...');
    await searchInput.fill('T1110');
    
    // Should only show one alert now
    await expect(page.getByText('T1110')).toBeVisible();
    await expect(page.getByText('T1059')).not.toBeVisible();
    
    const triageButtons = page.getByRole('link', { name: 'Triage' });
    await expect(triageButtons).toHaveCount(1);
  });

  test('should filter alerts by severity', async ({ page }) => {
    // Select Critical severity
    const severitySelect = page.locator('select').first();
    await severitySelect.selectOption('critical');
    
    // Should show T1110 which is critical, hide others
    await expect(page.getByText('T1110')).toBeVisible();
    await expect(page.getByText('T1059')).not.toBeVisible();
  });
});
