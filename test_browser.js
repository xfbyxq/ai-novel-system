const { chromium } = require('playwright');

async function testNovelSystem() {
  console.log('Starting browser automation test...');
  
  const browser = await chromium.launch({
    headless: false, // 显示浏览器窗口
    slowMo: 50 // 减慢操作速度以便观察
  });
  
  const page = await browser.newPage();
  
  try {
    // 1. 访问首页
    console.log('Navigating to home page...');
    await page.goto('http://localhost:3000', {
      waitUntil: 'networkidle' // 等待网络空闲
    });
    
    // 2. 检查页面标题
    const title = await page.title();
    console.log(`Page title: ${title}`);
    
    // 3. 等待页面加载完成
    console.log('Waiting for page to load...');
    await page.waitForTimeout(2000); // 等待 2 秒
    
    // 4. 截图保存
    await page.screenshot({
      path: 'test_screenshots/homepage.png',
      fullPage: true
    });
    console.log('Screenshot saved: test_screenshots/homepage.png');
    
    // 5. 检查页面内容
    const content = await page.content();
    console.log('Page content length:', content.length, 'characters');
    
    // 6. 寻找关键元素
    try {
      const heading = await page.$('h1, h2, h3');
      if (heading) {
        const headingText = await heading.textContent();
        console.log('Found heading:', headingText?.trim());
      }
    } catch (e) {
      console.log('No heading found');
    }
    
    console.log('\nTest completed successfully!');
    
  } catch (error) {
    console.error('Test failed:', error.message);
  } finally {
    // 关闭浏览器
    console.log('Closing browser...');
    await browser.close();
    console.log('Browser closed.');
  }
}

// 创建截图目录
const fs = require('fs');
if (!fs.existsSync('test_screenshots')) {
  fs.mkdirSync('test_screenshots', { recursive: true });
}

// 运行测试
testNovelSystem();