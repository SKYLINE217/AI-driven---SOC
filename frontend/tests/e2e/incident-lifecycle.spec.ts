import { test, expect } from '@playwright/test'

test.describe('Full Incident Lifecycle and RBAC', () => {
  test('Analyst cannot approve playbook, Approver can', async ({ page }) => {
    // 1. Login as Analyst
    await page.goto('/login')
    await page.click('button#login-analyst')
    
    // Wait for redirect to alerts and ensure connection is established
    await expect(page.locator('h1')).toContainText('Alert Queue')
    
    // 2. Navigate to an incident via triage button
    const triageButton = page.getByRole('link', { name: 'Triage' }).first()
    await triageButton.click()
    
    // Wait for Incident Detail to load
    await expect(page.getByText('Incident Detail', { exact: false })).toBeVisible()
    
    // 3. Click through all tabs
    await page.getByRole('button', { name: /Attack Graph/i }).click()
    await expect(page.getByText('Attack Path')).toBeVisible()
    
    await page.getByRole('button', { name: /MITRE/i }).click()
    await expect(page.getByText('Tactic:')).toBeVisible()
    
    await page.getByRole('button', { name: /Playbook/i }).click()
    
    // 4. Attempt to approve as Analyst - button should be disabled / restricted
    const restrictedButton = page.getByRole('button', { name: /Approve Playbook/i })
    await expect(restrictedButton).toBeDisabled()
    
    // 5. Sign out and login as Approver
    await page.goto('/settings')
    await page.getByRole('button', { name: /Sign Out/i }).click()
    
    await page.goto('/login')
    await page.click('button#login-approver')
    
    // 6. Navigate back to Incident Playbook tab
    await page.goto('/alerts')
    await page.getByRole('link', { name: 'Triage' }).first().click()
    await page.getByRole('button', { name: /Playbook/i }).click()
    
    // 7. Approve playbook
    const approveButton = page.getByRole('button', { name: 'Approve for Operations' })
    await expect(approveButton).toBeEnabled()
    
    // Playwright handling for the window.prompt
    page.on('dialog', dialog => dialog.accept('Playwright automated approval'))
    await approveButton.click()
    
    // 8. Verify approval success and ledger entry
    await expect(page.getByText('Approved by approver@example.com')).toBeVisible()
    
    await page.getByRole('button', { name: /Audit Trail/i }).click()
    await expect(page.getByText('playbook_approved')).toBeVisible()
    await expect(page.getByText('approver@example.com')).toBeVisible()
  })
})
