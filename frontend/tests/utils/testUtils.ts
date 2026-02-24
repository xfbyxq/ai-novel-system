import { Page, Locator } from '@playwright/test';

// 测试工具类
export class TestUtils {
  // 等待元素可见
  static async waitForVisible(locator: Locator, timeout: number = 30000) {
    await locator.waitFor({ state: 'visible', timeout });
  }

  // 等待元素隐藏
  static async waitForHidden(locator: Locator, timeout: number = 30000) {
    await locator.waitFor({ state: 'hidden', timeout });
  }

  // 登录操作
  static async login(page: Page, username: string = process.env.TEST_USERNAME || 'test@example.com', password: string = process.env.TEST_PASSWORD || 'test123456') {
    await page.goto('/login');
    
    await page.fill('input[name="username"]', username);
    await page.fill('input[name="password"]', password);
    await page.click('button[type="submit"]');
    
    // 等待登录成功并跳转到首页
    await page.waitForURL('/');
  }

  // 导航到指定页面
  static async navigateTo(page: Page, path: string) {
    await page.goto(path);
    await page.waitForLoadState('networkidle');
  }

  // 生成随机字符串
  static generateRandomString(length: number = 8): string {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let result = '';
    for (let i = 0; i < length; i++) {
      result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
  }

  // 检查页面标题
  static async checkPageTitle(page: Page, expectedTitle: string) {
    await page.waitForLoadState('domcontentloaded');
    const title = await page.title();
    expect(title).toContain(expectedTitle);
  }

  // 截图
  static async takeScreenshot(page: Page, name: string) {
    await page.screenshot({ path: `test-results/screenshots/${name}.png`, fullPage: true });
  }

  // 模拟网络延迟
  static async simulateNetworkDelay(page: Page, delay: number = 1000) {
    await page.context().setDefaultTimeout(delay + 5000);
    await new Promise(resolve => setTimeout(resolve, delay));
  }

  // 检查元素是否包含指定文本
  static async checkElementContainsText(locator: Locator, text: string) {
    await this.waitForVisible(locator);
    const elementText = await locator.textContent();
    expect(elementText).toContain(text);
  }

  // 检查元素是否存在
  static async checkElementExists(locator: Locator) {
    await this.waitForVisible(locator);
    const count = await locator.count();
    expect(count).toBeGreaterThan(0);
  }

  // 检查元素是否不存在
  static async checkElementNotExists(locator: Locator) {
    const count = await locator.count();
    expect(count).toBe(0);
  }
}
