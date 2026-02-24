#!/usr/bin/env node

import fs from 'fs';
import path from 'path';

// 生成测试报告
function generateTestReport() {
  const currentDir = process.cwd();
  const testResultsDir = path.join(currentDir, 'test-results');
  const reportPath = path.join(testResultsDir, 'report.md');
  
  // 创建测试结果目录
  if (!fs.existsSync(testResultsDir)) {
    fs.mkdirSync(testResultsDir, { recursive: true });
  }
  
  // 读取测试结果
  let testResults = {};
  try {
    const resultsPath = path.join(testResultsDir, 'results.json');
    console.log(`读取测试结果文件: ${resultsPath}`);
    if (fs.existsSync(resultsPath)) {
      console.log('测试结果文件存在，正在读取...');
      const data = fs.readFileSync(resultsPath, 'utf8');
      testResults = JSON.parse(data);
      console.log('读取测试结果成功');
      if (testResults.suites) {
        console.log(`包含 ${testResults.suites.length} 个测试套件`);
      }
    } else {
      console.log('测试结果文件不存在');
    }
  } catch (error) {
    console.error('读取测试结果失败:', error);
  }
  
  // 生成报告内容
  const reportContent = generateReportContent(testResults);
  
  // 写入报告文件
  fs.writeFileSync(reportPath, reportContent);
  console.log(`测试报告已生成: ${reportPath}`);
}

// 生成报告内容
function generateReportContent(testResults) {
  const now = new Date();
  const timestamp = now.toISOString();
  
  let content = `# 前端UI自动化测试报告

## 测试概览

- 测试时间: ${timestamp}
- 测试框架: Playwright
- 测试环境: ${process.env.NODE_ENV || 'development'}
- 基础URL: ${process.env.BASE_URL || 'http://localhost:3000'}

`;
  
  // 测试结果统计
  if (testResults.suites) {
    let passed = 0;
    let failed = 0;
    let skipped = 0;
    
    // 遍历所有测试套件
    for (const suite of testResults.suites) {
      // 遍历所有测试用例
      for (const spec of suite.specs) {
        // 遍历所有测试执行
        for (const test of spec.tests) {
          // 遍历所有测试结果
          for (const result of test.results) {
            if (result.status === 'passed') {
              passed++;
            } else if (result.status === 'failed') {
              failed++;
            } else if (result.status === 'skipped') {
              skipped++;
            }
          }
        }
      }
    }
    
    const total = passed + failed + skipped;
    
    content += `## 测试结果统计

| 状态 | 数量 | 百分比 |
|------|------|--------|
| 通过 | ${passed} | ${((passed / total) * 100).toFixed(2)}% |
| 失败 | ${failed} | ${((failed / total) * 100).toFixed(2)}% |
| 跳过 | ${skipped} | ${((skipped / total) * 100).toFixed(2)}% |
| 总计 | ${total} | 100% |

`;
    
    // 失败测试详情
    if (failed > 0) {
      content += `## 失败测试详情

`;
      let index = 1;
      
      // 遍历所有测试套件
      for (const suite of testResults.suites) {
        // 遍历所有测试用例
        for (const spec of suite.specs) {
          // 遍历所有测试执行
          for (const test of spec.tests) {
            // 遍历所有测试结果
            for (const result of test.results) {
              if (result.status === 'failed') {
                content += `### ${index}. ${suite.file}

`;
                content += `**测试名称:** ${spec.title}

`;
                if (result.errors && result.errors.length > 0) {
                  content += `**失败原因:** ${result.errors[0].message}

`;
                  if (result.errors[0].stack) {
                    content += `**错误堆栈:**

${result.errors[0].stack}


`;
                  }
                }
                index++;
              }
            }
          }
        }
      }
    }
  } else {
    content += `## 测试结果统计

暂无测试结果数据

`;
  }
  
  // 测试建议
  content += `## 测试建议

1. **定期运行测试**: 建议在每次代码提交和部署前运行自动化测试
2. **扩展测试覆盖**: 逐步增加测试用例，覆盖更多页面和功能
3. **性能测试**: 考虑添加性能测试，监控页面加载速度和响应时间
4. **兼容性测试**: 确保在不同浏览器和设备上的兼容性
5. **安全性测试**: 定期进行安全性测试，确保系统安全

`;
  
  return content;
}

// 运行报告生成
if (import.meta.url === `file://${process.argv[1]}`) {
  generateTestReport();
}

export { generateTestReport };
