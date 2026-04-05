"""调试选择器测试."""
from playwright.sync_api import Page


def test_debug_selectors(page: Page):
    """调试选择器问题."""
    # 访问页面并打开创建模态框
    page.goto("http://localhost:3000/novels")
    page.wait_for_load_state("networkidle", timeout=10000)

    # 点击创建按钮
    create_button = page.get_by_text("创建小说")
    create_button.click()

    # 等待模态框出现
    page.locator(".ant-modal-title").wait_for(state="visible", timeout=5000)

    print("=== 调试图形化选择器 ===")

    # 截图整个模态框
    page.locator(".ant-modal").screenshot(path="modal_debug.png")
    print("模态框截图已保存为 modal_debug.png")

    # 尝试不同的选择器来定位类型选择框
    selectors_to_try = [
        ".ant-modal .ant-select",
        ".ant-modal .ant-select:has(.ant-select-selector)",
        ".ant-modal .ant-select-single",
        ".ant-modal [aria-label='类型']",
        ".ant-modal .ant-form-item:has(label:text('类型')) .ant-select",
        "div.ant-form-item:has(label:text('类型')) div.ant-select"
    ]

    for i, selector in enumerate(selectors_to_try):
        elements = page.locator(selector).all()
        print(f"选择器 {i+1}: '{selector}' - 找到 {len(elements)} 个元素")
        for j, elem in enumerate(elements):
            try:
                is_visible = elem.is_visible()
                bounding_box = elem.bounding_box()
                print(f"  元素 {j}: 可见={is_visible}, 位置={bounding_box}")
                if is_visible and bounding_box:
                    # 对每个找到的元素截图
                    elem.screenshot(path=f"element_{i}_{j}.png")
                    print(f"    截图保存为 element_{i}_{j}.png")
            except Exception as e:
                print(f"  元素 {j}: 错误 - {e}")

    # 尝试通过标签文本定位
    print("\n=== 通过标签文本定位 ===")
    labels = page.locator("label").all()
    for label in labels:
        try:
            text = label.text_content()
            if text and "类型" in text:
                print(f"找到包含'类型'的标签: '{text}'")
                # 尝试找到关联的选择框
                select_boxes = label.locator("xpath=following::div[contains(@class, 'ant-select')]").all()
                print(f"  关联的选择框数量: {len(select_boxes)}")
        except:
            pass

    # 尝试手动点击方式
    print("\n=== 手动点击测试 ===")
    try:
        # 直接点击坐标位置（假设类型选择框在特定位置）
        page.mouse.click(400, 250)  # 根据模态框布局估计的位置
        page.wait_for_timeout(1000)

        # 检查是否有下拉选项出现
        dropdown_options = page.locator(".ant-select-dropdown .ant-select-item").all()
        print(f"下拉选项数量: {len(dropdown_options)}")
        for option in dropdown_options:
            try:
                print(f"  选项: {option.text_content()}")
            except:
                pass

    except Exception as e:
        print(f"手动点击失败: {e}")

    page.wait_for_timeout(3000)  # 保持页面打开以便观察