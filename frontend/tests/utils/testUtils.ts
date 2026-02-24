import { Page, Locator, expect } from '@playwright/test';

export class TestUtils {
  static async waitForVisible(locator: Locator, timeout: number = 30000) {
    await locator.waitFor({ state: 'visible', timeout });
  }

  static async waitForHidden(locator: Locator, timeout: number = 30000) {
    await locator.waitFor({ state: 'hidden', timeout });
  }

  static async login(page: Page, username: string = process.env.TEST_USERNAME || 'test@example.com', password: string = process.env.TEST_PASSWORD || 'test123456') {
    await page.goto('/login');
    
    await page.fill('input[name="username"]', username);
    await page.fill('input[name="password"]', password);
    await page.click('button[type="submit"]');
    
    await page.waitForURL('/');
  }

  static async navigateTo(page: Page, path: string) {
    await page.goto(path);
    await page.waitForLoadState('networkidle');
  }

  static generateRandomString(length: number = 8): string {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let result = '';
    for (let i = 0; i < length; i++) {
      const randomIndex = Math.floor(Math.random() * chars.length);
      result += chars.charAt(randomIndex);
    }
    return result;
  }

  static async checkPageTitle(page: Page, expectedTitle: string) {
    await page.waitForLoadState('domcontentloaded');
    const title = await page.title();
    expect(title).toContain(expectedTitle);
  }

  static async takeScreenshot(page: Page, name: string) {
    await page.screenshot({ path: `test-results/screenshots/${name}.png`, fullPage: true });
  }

  static async simulateNetworkDelay(page: Page, delay: number = 1000) {
    page.context().setDefaultTimeout(delay + 5000);
    await new Promise<void>(resolve => setTimeout(resolve, delay));
  }

  static async checkElementContainsText(locator: Locator, text: string) {
    await this.waitForVisible(locator);
    const elementText = await locator.textContent();
    expect(elementText).toContain(text);
  }

  static async checkElementExists(locator: Locator) {
    await this.waitForVisible(locator);
    const count = await locator.count();
    expect(count).toBeGreaterThan(0);
  }

  static async checkElementNotExists(locator: Locator) {
    const count = await locator.count();
    expect(count).toBe(0);
  }
}
