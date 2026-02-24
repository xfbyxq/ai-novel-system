const { chromium } = require('playwright');

async function testNovelManagement() {
  console.log('=== Testing Novel Management Module ===');
  
  const browser = await chromium.launch({
    headless: false,
    slowMo: 50
  });
  
  const page = await browser.newPage();
  
  try {
    // 1. 访问首页
    console.log('1. Navigating to home page...');
    await page.goto('http://localhost:3000', {
      waitUntil: 'networkidle'
    });
    
    // 2. 等待页面加载
    await page.waitForTimeout(1000);
    
    // 3. 查找并点击小说管理
    console.log('2. Finding novel management...');
    
    // 尝试通过不同方式找到小说管理入口
    let novelLink = null;
    
    try {
      // 尝试通过文本查找
      novelLink = await page.$('a:has-text("小说")');
    } catch (e) {
      console.log('No direct link found, checking navigation');
    }
    
    if (novelLink) {
      console.log('Found novel link, clicking...');
      await novelLink.click();
    } else {
      console.log('No novel link found, checking page content');
    }
    
    // 4. 等待页面变化
    await page.waitForTimeout(2000);
    
    // 5. 截图
    await page.screenshot({
      path: 'test_screenshots/novel_management.png',
      fullPage: true
    });
    console.log('Screenshot saved: test_screenshots/novel_management.png');
    
    // 6. 检查页面URL
    const url = page.url();
    console.log('Current URL:', url);
    
    // 7. 检查页面内容
    const content = await page.content();
    console.log('Page contains "小说":', content.includes('小说'));
    
  } catch (error) {
    console.error('Novel management test failed:', error.message);
  } finally {
    await browser.close();
  }
}

async function testCrawlerModule() {
  console.log('\n=== Testing Crawler Module ===');
  
  const browser = await chromium.launch({
    headless: false,
    slowMo: 50
  });
  
  const page = await browser.newPage();
  
  try {
    // 1. 访问首页
    console.log('1. Navigating to home page...');
    await page.goto('http://localhost:3000', {
      waitUntil: 'networkidle'
    });
    
    // 2. 等待页面加载
    await page.waitForTimeout(1000);
    
    // 3. 查找并点击爬虫任务
    console.log('2. Finding crawler tasks...');
    
    let crawlerLink = null;
    
    try {
      crawlerLink = await page.$('a:has-text("爬虫")');
    } catch (e) {
      console.log('No crawler link found');
    }
    
    if (crawlerLink) {
      console.log('Found crawler link, clicking...');
      await crawlerLink.click();
    } else {
      console.log('No crawler link found, checking page content');
    }
    
    // 4. 等待页面变化
    await page.waitForTimeout(2000);
    
    // 5. 截图
    await page.screenshot({
      path: 'test_screenshots/crawler_module.png',
      fullPage: true
    });
    console.log('Screenshot saved: test_screenshots/crawler_module.png');
    
    // 6. 检查页面URL
    const url = page.url();
    console.log('Current URL:', url);
    
  } catch (error) {
    console.error('Crawler module test failed:', error.message);
  } finally {
    await browser.close();
  }
}

// 创建截图目录
const fs = require('fs');
if (!fs.existsSync('test_screenshots')) {
  fs.mkdirSync('test_screenshots', { recursive: true });
}

// 运行测试
async function runAllTests() {
  console.log('Starting comprehensive UI tests...\n');
  
  await testNovelManagement();
  await testCrawlerModule();
  
  console.log('\n=== All Tests Completed ===');
}

runAllTests();