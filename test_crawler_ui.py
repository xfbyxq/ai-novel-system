#!/usr/bin/env python3
"""爬虫模块 UI 自动化测试"""
import asyncio
from playwright.async_api import async_playwright

async def test_crawler_module_ui():
    """测试爬虫模块 UI"""
    async with async_playwright() as p:
        # 启动浏览器
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            # 导航到前端页面
            await page.goto("http://localhost:3002/")
            print("成功导航到前端页面")
            
            # 等待页面加载完成
            await page.wait_for_load_state("networkidle")
            
            # 截图保存
            await page.screenshot(path="test_screenshots/homepage.png", full_page=True)
            print("保存首页截图")
            
            # 打印页面标题和URL
            print(f"页面标题: {await page.title()}")
            print(f"当前URL: {page.url}")
            
            # 打印页面内容（前500个字符）
            content = await page.content()
            print(f"页面内容预览: {content[:500]}...")
            
            # 检查是否有错误信息
            error_message = page.locator(".error")
            if await error_message.is_visible():
                print(f"页面错误信息: {await error_message.text_content()}")
            
            # 检查页面上的所有元素
            print("\n检查页面元素:")
            
            # 检查是否有导航栏
            navbar = page.locator(".navbar, .nav, .navigation")
            if await navbar.is_visible():
                print("找到导航栏")
                # 打印导航栏中的所有元素
                nav_elements = navbar.locator("*").filter(has_text=True)
                nav_count = await nav_elements.count()
                print(f"导航栏中的元素: {nav_count}")
                for i in range(nav_count):
                    element = nav_elements.nth(i)
                    text = await element.text_content()
                    print(f"  - {text}")
            else:
                print("未找到导航栏")
            
            # 检查是否有菜单按钮
            menu_button = page.locator(".menu-button, .hamburger, .menu-icon")
            if await menu_button.is_visible():
                print("找到菜单按钮")
                await menu_button.click()
                await page.wait_for_load_state("networkidle")
                print("点击了菜单按钮")
                
                # 检查是否有下拉菜单
                dropdown_menu = page.locator(".dropdown-menu, .menu-dropdown")
                if await dropdown_menu.is_visible():
                    print("找到下拉菜单")
                    # 打印菜单中的所有链接
                    menu_links = dropdown_menu.locator("a")
                    menu_link_count = await menu_links.count()
                    print(f"菜单中的链接: {menu_link_count}")
                    for i in range(menu_link_count):
                        link = menu_links.nth(i)
                        text = await link.text_content()
                        href = await link.get_attribute("href")
                        print(f"  - {text} ({href})")
                        if "crawler" in href.lower() or "task" in href.lower():
                            await link.click()
                            await page.wait_for_load_state("networkidle")
                            print(f"成功导航到: {text}")
                            break
            else:
                print("未找到菜单按钮")
            
            # 尝试直接导航到爬虫任务页面
            print("\n尝试直接导航到爬虫任务页面...")
            await page.goto("http://localhost:3002/crawler-tasks")
            await page.wait_for_load_state("networkidle")
            print(f"导航到: {page.url}")
            
            # 截图保存
            await page.screenshot(path="test_screenshots/crawler_tasks_direct.png", full_page=True)
            print("保存直接导航后的截图")
            
            # 截图保存
            await page.screenshot(path="test_screenshots/crawler_tasks.png", full_page=True)
            print("保存爬虫任务页面截图")
            
            # 打印当前页面信息
            print(f"\n当前页面标题: {await page.title()}")
            print(f"当前页面URL: {page.url}")
            
            # 打印页面内容（前500个字符）
            content = await page.content()
            print(f"页面内容预览: {content[:500]}...")
            
            # 检查页面上的所有按钮
            print("\n页面上的按钮:")
            buttons = page.locator("button")
            button_count = await buttons.count()
            print(f"找到 {button_count} 个按钮")
            for i in range(button_count):
                button = buttons.nth(i)
                text = await button.text_content()
                print(f"  - {text}")
            
            # 检查页面上的所有表单元素
            print("\n页面上的表单元素:")
            form_elements = page.locator("input, select, textarea")
            form_element_count = await form_elements.count()
            print(f"找到 {form_element_count} 个表单元素")
            for i in range(form_element_count):
                element = form_elements.nth(i)
                type = await element.get_attribute("type")
                name = await element.get_attribute("name")
                placeholder = await element.get_attribute("placeholder")
                print(f"  - {type} ({name}): {placeholder}")
            
            # 检查页面上的所有文本内容
            print("\n页面上的文本内容:")
            text_elements = page.locator("*").filter(has_text=True)
            text_element_count = await text_elements.count()
            print(f"找到 {text_element_count} 个文本元素")
            # 打印前10个文本元素
            for i in range(min(10, text_element_count)):
                element = text_elements.nth(i)
                text = await element.text_content()
                print(f"  - {text[:100]}...")
            
            # 测试创建任务
            print("\n测试创建任务...")
            
            # 尝试找到并点击创建任务按钮
            create_button = page.locator("text=Create Task")
            if await create_button.is_visible():
                print("找到创建任务按钮，点击它")
                await create_button.click()
                await page.wait_for_load_state("networkidle")
                
                # 填写任务表单
                task_name_input = page.locator("input[name=task_name]")
                if await task_name_input.is_visible():
                    await task_name_input.fill("测试爬虫任务")
                    print("填写任务名称")
                else:
                    print("未找到任务名称输入框")
                
                # 选择任务类型
                crawl_type_select = page.locator("select[name=crawl_type]")
                if await crawl_type_select.is_visible():
                    await crawl_type_select.select_option("ranking")
                    print("选择任务类型为 ranking")
                else:
                    print("未找到任务类型选择器")
                
                # 选择平台
                platform_select = page.locator("select[name=platform]")
                if await platform_select.is_visible():
                    await platform_select.select_option("qidian")
                    print("选择平台为 qidian")
                else:
                    print("未找到平台选择器")
                
                # 提交表单
                submit_button = page.locator("text=Submit")
                if await submit_button.is_visible():
                    await submit_button.click()
                    print("提交任务表单")
                    
                    # 等待任务创建成功
                    await page.wait_for_load_state("networkidle")
                    
                    # 检查是否有成功消息
                    success_message = page.locator(".success-message")
                    if await success_message.is_visible():
                        print("任务创建成功")
                    else:
                        print("任务创建可能失败")
                else:
                    print("未找到提交按钮")
                
                # 截图保存
                await page.screenshot(path="test_screenshots/task_created.png", full_page=True)
                print("保存任务创建页面截图")
            else:
                print("未找到创建任务按钮")
            
        except Exception as e:
            print(f"测试过程中出错: {e}")
            # 保存错误时的截图
            await page.screenshot(path="test_screenshots/error.png", full_page=True)
        finally:
            # 关闭浏览器
            await browser.close()
            print("测试完成，浏览器已关闭")

if __name__ == "__main__":
    asyncio.run(test_crawler_module_ui())
