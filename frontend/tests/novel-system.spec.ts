import { test, expect } from '@playwright/test';

test('首页加载测试', async ({ page }) => {
  await page.goto('/');
  
  // 等待页面加载完成
  await expect(page).toHaveTitle(/AI 小说生成系统/);
  
  // 检查主要导航元素
  await expect(page.locator('.ant-menu')).toBeVisible();
  
  // 检查页面内容是否加载完整
  await expect(page.locator('h4')).toContainText('仪表盘');
});

test('完整导航测试', async ({ page }) => {
  await page.goto('/');
  
  // 测试导航到仪表盘
  await page.locator('.ant-menu-item', { hasText: '仪表盘' }).click();
  await expect(page).toHaveURL('/');
  await expect(page.locator('h4')).toContainText('仪表盘');
  
  // 测试导航到小说管理
  await page.locator('.ant-menu-item', { hasText: '小说管理' }).click();
  await expect(page).toHaveURL(/novels/);
  await expect(page.locator('.ant-table')).toBeVisible();
  
  // 测试导航到爬虫任务
  await page.locator('.ant-menu-item', { hasText: '爬虫任务' }).click();
  await expect(page).toHaveURL(/crawler/);
  
  // 测试导航到市场数据
  await page.locator('.ant-menu-item', { hasText: '市场数据' }).click();
  await expect(page).toHaveURL(/market-data/);
  
  // 测试导航到平台账号
  await page.locator('.ant-menu-item', { hasText: '平台账号' }).click();
  await expect(page).toHaveURL(/accounts/);
  
  // 测试导航到发布管理
  await page.locator('.ant-menu-item', { hasText: '发布管理' }).click();
  await expect(page).toHaveURL(/publish/);
  
  // 测试导航到系统监控
  await page.locator('.ant-menu-item', { hasText: '系统监控' }).click();
  await expect(page).toHaveURL(/monitoring/);
});

test('路由跳转正确性测试', async ({ page }) => {
  // 直接访问小说管理页面
  await page.goto('/novels');
  await expect(page).toHaveURL(/novels/);
  await expect(page.locator('.ant-table')).toBeVisible();
  
  // 直接访问爬虫任务页面
  await page.goto('/crawler');
  await expect(page).toHaveURL(/crawler/);
  
  // 直接访问市场数据页面
  await page.goto('/market-data');
  await expect(page).toHaveURL(/market-data/);
  
  // 直接访问平台账号页面
  await page.goto('/accounts');
  await expect(page).toHaveURL(/accounts/);
  
  // 直接访问发布管理页面
  await page.goto('/publish');
  await expect(page).toHaveURL(/publish/);
  
  // 直接访问系统监控页面
  await page.goto('/monitoring');
  await expect(page).toHaveURL(/monitoring/);
});

test('页面加载完整性测试', async ({ page }) => {
  // 测试仪表盘页面加载完整性
  await page.goto('/');
  await expect(page).toHaveTitle(/AI 小说生成系统/);
  await expect(page.locator('.ant-menu')).toBeVisible();
  await expect(page.locator('h4')).toContainText('仪表盘');
  
  // 测试小说管理页面加载完整性
  await page.goto('/novels');
  await expect(page.locator('.ant-table')).toBeVisible();
  
  // 测试爬虫任务页面加载完整性
  await page.goto('/crawler');
  
  // 测试市场数据页面加载完整性
  await page.goto('/market-data');
  
  // 测试平台账号页面加载完整性
  await page.goto('/accounts');
  
  // 测试发布管理页面加载完整性
  await page.goto('/publish');
  
  // 测试系统监控页面加载完整性
  await page.goto('/monitoring');
});

test('嵌套路由测试', async ({ page }) => {
  // 测试小说详情页面路由
  await page.goto('/novels/1');
  await expect(page).toHaveURL(/novels\/1/);
  
  // 测试章节阅读页面路由
  await page.goto('/novels/1/chapters/1');
  await expect(page).toHaveURL(/novels\/1\/chapters\/1/);
});

test('404页面测试', async ({ page }) => {
  // 测试不存在的路由
  await page.goto('/non-existent-path');
  await expect(page.locator('.ant-result')).toBeVisible();
  await expect(page.locator('.ant-result-title')).toContainText('404');
});
