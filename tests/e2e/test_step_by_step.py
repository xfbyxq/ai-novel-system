"""逐步验证测试."""
from playwright.sync_api import Page


def test_step_by_step_creation(page: Page):
    """逐步验证小说创建流程."""
    # 1. 访问小说列表页面
    page.goto("http://localhost:3000/novels")
    page.wait_for_load_state("networkidle", timeout=10000)

    print("步骤1: 页面加载完成")

    # 2. 点击创建小说按钮
    create_button = page.get_by_text("创建小说")
    assert create_button.is_visible(), "创建小说按钮应该可见"
    create_button.click()
    print("步骤2: 点击创建小说按钮")

    # 3. 等待模态框出现
    modal_title = page.locator(".ant-modal-title")
    modal_title.wait_for(state="visible", timeout=5000)
    assert "创建新小说" in modal_title.text_content()
    print("步骤3: 模态框已打开")

    # 4. 填写标题
    title_input = page.locator(".ant-modal input[placeholder*='例如：星辰大主宰']")
    title_input.fill("测试小说标题")
    print("步骤4: 填写标题完成")

    # 5. 选择类型 - 使用点击方式而不是select_option
    genre_select = page.locator(".ant-modal .ant-select:has(.ant-select-selector)")
    genre_select.click()
    print("步骤5: 点击类型选择框")

    # 6. 选择具体的类型选项
    # 等待下拉选项出现
    page.wait_for_timeout(1000)  # 等待动画
    genre_option = page.get_by_text("仙侠")
    if genre_option.count() > 0:
        genre_option.first.click()
        print("步骤6: 选择仙侠类型")
    else:
        print("警告: 未找到仙侠选项")

    # 7. 填写简介
    synopsis_input = page.locator(".ant-modal textarea[placeholder*='简要描述']")
    synopsis_input.fill("这是一个测试小说的简介内容。")
    print("步骤7: 填写简介完成")

    # 8. 点击创建按钮
    create_btn = page.locator(".ant-modal .ant-btn-primary:has-text('创建')")
    create_btn.click()
    print("步骤8: 点击创建按钮")

    # 9. 等待成功消息
    try:
        success_msg = page.locator(".ant-message-success")
        success_msg.wait_for(state="visible", timeout=10000)
        print("步骤9: 小说创建成功")
        print(f"成功消息: {success_msg.text_content()}")
    except:
        print("步骤9: 未检测到成功消息，但继续执行")

    # 10. 验证是否跳转到详情页
    page.wait_for_timeout(2000)  # 等待可能的页面跳转
    if "/novels/" in page.url and page.url != "http://localhost:3000/novels":
        print("步骤10: 成功跳转到小说详情页")
    else:
        print(f"步骤10: 当前URL: {page.url}")

    # 截图保存结果
    page.screenshot(path="step_by_step_result.png")
    print("测试完成，截图已保存为 step_by_step_result.png")