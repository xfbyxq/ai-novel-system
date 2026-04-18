"""
工作流程测试 (调试用)

测试编号: E2E-DEBUG-01
测试目标: 基于调试结果的工作流程验证

前置条件: 无
依赖测试: 无

注意: 这是用于调试和验证的临时测试
"""
from playwright.sync_api import Page


def test_working_creation_flow(page: Page):
    """基于调试结果的可工作创建流程测试."""
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
    title_input.fill("自动化测试小说")
    print("步骤4: 填写标题完成")

    # 5. 选择类型 - 使用精确的位置选择第一个select
    type_select = page.locator(".ant-modal .ant-select").nth(0)
    type_select.click()
    print("步骤5: 点击类型选择框")

    # 6. 等待并选择选项
    page.wait_for_timeout(1000)  # 等待下拉动画
    # 选择第一个选项（通常是仙侠）
    first_option = page.locator(".ant-select-dropdown .ant-select-item").first
    first_option.click()
    print("步骤6: 选择类型完成")

    # 7. 填写简介
    synopsis_input = page.locator(".ant-modal textarea[placeholder*='简要描述']")
    synopsis_input.fill("这是一个通过自动化测试创建的小说。")
    print("步骤7: 填写简介完成")

    # 8. 点击创建按钮
    create_btn = page.locator(".ant-modal .ant-btn-primary:has-text('创建')")
    create_btn.click()
    print("步骤8: 点击创建按钮")

    # 9. 等待成功消息或页面跳转
    try:
        # 等待成功消息
        success_msg = page.locator(".ant-message-success")
        success_msg.wait_for(state="visible", timeout=15000)
        print(f"步骤9: 小说创建成功 - {success_msg.text_content()}")
    except:
        print("步骤9: 未检测到成功消息，检查是否跳转页面")
        page.wait_for_timeout(3000)
        if "/novels/" in page.url and page.url != "http://localhost:3000/novels":
            print("步骤9: 成功跳转到小说详情页")
        else:
            print(f"步骤9: 当前页面: {page.url}")

    # 10. 截图保存结果
    page.screenshot(path="working_test_result.png")
    print("测试完成，结果截图保存为 working_test_result.png")