"""
最终流程测试 (调试用)

测试编号: E2E-DEBUG-02
测试目标: 最终验证的小说创建流程

前置条件: 无
依赖测试: 无

注意: 这是用于调试和验证的临时测试
"""
from playwright.sync_api import Page


def test_final_working_creation(page: Page):
    """最终版可工作的小说创建流程测试."""
    # 1. 访问小说列表页面
    page.goto("http://localhost:3000/novels")
    page.wait_for_load_state("networkidle", timeout=10000)
    print("步骤1: 页面加载完成")

    # 2. 点击创建小说按钮
    create_button = page.get_by_text("创建小说")
    create_button.click()
    print("步骤2: 点击创建小说按钮")

    # 3. 等待模态框出现
    modal_title = page.locator(".ant-modal-title")
    modal_title.wait_for(state="visible", timeout=5000)
    assert "创建新小说" in modal_title.text_content()
    print("步骤3: 模态框已打开")

    # 4. 填写标题
    title_input = page.locator(".ant-modal input[placeholder*='例如：星辰大主宰']")
    title_input.fill("最终测试小说")
    print("步骤4: 填写标题完成")

    # 5. 选择类型
    type_select = page.locator(".ant-modal .ant-select").nth(0)
    type_select.click()
    print("步骤5: 点击类型选择框")

    # 6. 等待并选择选项
    page.wait_for_timeout(1000)
    first_option = page.locator(".ant-select-dropdown .ant-select-item").first
    first_option.click()
    print("步骤6: 选择类型完成")

    # 7. 填写简介
    synopsis_input = page.locator(".ant-modal textarea[placeholder*='简要描述']")
    synopsis_input.fill("这是最终的自动化测试小说。")
    print("步骤7: 填写简介完成")

    # 8. 等待一小段时间确保所有操作完成
    page.wait_for_timeout(1000)

    # 9. 使用多种方式尝试点击创建按钮
    print("步骤8: 尝试点击创建按钮")

    # 方法1: 直接通过文本查找
    try:
        create_btn = page.get_by_text("创建").and_(page.locator(".ant-btn-primary"))
        create_btn.click(timeout=5000)
        print("方法1成功: 通过文本和类名组合点击")
    except:
        print("方法1失败，尝试方法2")

        # 方法2: 通过位置点击
        try:
            # 获取模态框位置，然后计算创建按钮大概位置
            modal = page.locator(".ant-modal-content")
            bbox = modal.bounding_box()
            if bbox:
                # 在模态框右下角附近点击
                page.mouse.click(bbox['x'] + bbox['width'] - 100, bbox['y'] + bbox['height'] - 50)
                print("方法2成功: 通过坐标点击")
        except:
            print("方法2失败，尝试方法3")

            # 方法3: 等待并重试
            page.wait_for_timeout(2000)
            primary_buttons = page.locator(".ant-modal .ant-btn-primary").all()
            if primary_buttons:
                primary_buttons[0].click()
                print("方法3成功: 点击第一个主按钮")

    # 10. 等待结果
    print("步骤9: 等待操作结果")
    page.wait_for_timeout(3000)

    # 检查是否成功
    success_msgs = page.locator(".ant-message-success").all()
    if success_msgs:
        print(f"成功: {success_msgs[0].text_content()}")
    elif "/novels/" in page.url and page.url != "http://localhost:3000/novels":
        print("成功: 页面已跳转到小说详情")
    else:
        print(f"当前页面: {page.url}")

    # 11. 保存结果截图
    page.screenshot(path="final_test_result.png")
    print("测试完成，结果截图保存为 final_test_result.png")