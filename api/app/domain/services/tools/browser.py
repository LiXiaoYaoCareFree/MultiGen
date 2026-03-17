from typing import Optional

from app.domain.external.browser import Browser
from app.domain.models.tool_result import ToolResult
from .base import BaseTool, tool


class BrowserTool(BaseTool):
    """浏览器工具"""
    name: str = "browser"

    def __init__(self, browser: Browser) -> None:
        """构造函数，完成浏览器工具的初始化"""
        super().__init__()
        self.browser = browser

    @tool(
        name="browser_view",
        description="查看当前浏览器页面内容，用于确认已打开页面的最新状态。",
        parameters={},
        required=[]
    )
    async def browser_view(self) -> ToolResult:
        """获取浏览器当前网页内容并返回"""
        return await self.browser.view_page()

    @tool(
        name="browser_navigate",
        description="将浏览器导航至指定网址，当需要访问新页面时使用。",
        parameters={
            "url": {
                "type": "string",
                "description": "要访问的完整URL，必须包含协议前缀(如https://)"
            }
        },
        required=["url"]
    )
    async def browser_navigate(self, url: str) -> ToolResult:
        """传递url地址，使用浏览器导航到对应页面"""
        return await self.browser.navigate(url)

    @tool(
        name="browser_restart",
        description="重新启动浏览器并导航至指定URL，当需要重置浏览器时使用。",
        parameters={
            "url": {
                "type": "string",
                "description": "要访问的完整URL，必须包含协议前缀(如https://)"
            }
        },
        required=["url"]
    )
    async def browser_restart(self, url: str) -> ToolResult:
        """重启浏览器并导航到指定页面后返回页面内容"""
        return await self.browser.restart(url)

    @tool(
        name="browser_click",
        description="点击当前页面中的元素，在需要点击页面元素时使用。",
        parameters={
            "index": {
                "type": "integer",
                "description": "(可选)需要点击的元素索引"
            },
            "coordinate_x": {
                "type": "number",
                "description": "(可选)点击位置的x坐标"
            },
            "coordinate_y": {
                "type": "number",
                "description": "(可选)点击位置的y坐标"
            }
        },
        required=[],
    )
    async def browser_click(
            self,
            index: Optional[int] = None,
            coordinate_x: Optional[float] = None,
            coordinate_y: Optional[float] = None,
    ) -> ToolResult:
        """传递页面元素索引或者页面xy坐标点击对应元素"""
        return await self.browser.click(index, coordinate_x, coordinate_y)

    @tool(
        name="browser_input",
        description="覆盖浏览器当前页面可编辑区域的文本(input/textarea输入框)，在需要填充输入框时使用。",
        parameters={
            "text": {
                "type": "string",
                "description": "要填充到输入框的完整文本内容",
            },
            "press_enter": {
                "type": "boolean",
                "description": "输入后是否按下回车键",
            },
            "index": {
                "type": "integer",
                "description": "(可选)需要填充文本的元素索引"
            },
            "coordinate_x": {
                "type": "number",
                "description": "(可选)需要填充文本元素的x坐标"
            },
            "coordinate_y": {
                "type": "number",
                "description": "(可选)需要填充文本元素的y坐标"
            },
        },
        required=["text", "press_enter"],
    )
    async def browser_input(
            self,
            text: str,
            press_enter: bool,
            index: Optional[int] = None,
            coordinate_x: Optional[float] = None,
            coordinate_y: Optional[float] = None,
    ) -> ToolResult:
        """根据传递的元素索引或xy坐标，实现浏览器内容输入"""
        return await self.browser.input(text, press_enter, index, coordinate_x, coordinate_y)

    @tool(
        name="browser_move_mouse",
        description="将鼠标光标移动至当前浏览器页面的指定位置，用于模拟用户的鼠标移动",
        parameters={
            "coordinate_x": {
                "type": "number",
                "description": "目标光标位置的x坐标"
            },
            "coordinate_y": {
                "type": "number",
                "description": "目标光标位置的y坐标"
            },
        },
        required=["coordinate_x", "coordinate_y"],
    )
    async def browser_move_mouse(self, coordinate_x: float, coordinate_y: float) -> ToolResult:
        """传递xy坐标移动浏览器鼠标"""
        return await self.browser.move_mouse(coordinate_x, coordinate_y)

    @tool(
        name="browser_press_key",
        description="在当前浏览器页面模拟按键，当需要执行特定的键盘操作时使用。",
        parameters={
            "key": {
                "type": "string",
                "description": "要模拟的按键名称(例如: Enter、Tab、ArrowUp)，支持组合键(例如: Control+Enter)",
            },
        },
        required=["key"],
    )
    async def browser_press_key(self, key: str) -> ToolResult:
        """在浏览器页面模拟按键"""
        return await self.browser.press_key(key)

    @tool(
        name="browser_select_option",
        description="从当前浏览器页面的下拉列表元素中选择指定选项，用于选择下拉菜单中的选项",
        parameters={
            "index": {
                "type": "integer",
                "description": "需要操作的下拉列表元素的索引号(序号)"
            },
            "option": {
                "type": "integer",
                "description": "要选择的选项序号，从0开始(注: 指下拉框里的第几项)。"
            },
        },
        required=["index", "option"]
    )
    async def browser_select_option(self, index: int, option: int) -> ToolResult:
        """传递索引+下拉元素选项序号执行选择"""
        return await self.browser.select_option(index, option)

    @tool(
        name="browser_scroll_up",
        description="向上滚动浏览器页面，用于查看上方内容或返回页面顶部。",
        parameters={
            "to_top": {
                "type": "boolean",
                "description": "(可选)是否直接滚动到页面顶部，而非向上滚动一屏。"
            }
        },
        required=[]
    )
    async def browser_scroll_up(self, to_top: Optional[bool] = None) -> ToolResult:
        """向上滚动当前浏览器页面，支持滚动一页或者滚动到顶部"""
        return await self.browser.scroll_up(to_top)

    @tool(
        name="browser_scroll_down",
        description="向下滚动当前浏览器页面，用于查看下方内容或跳转到页面底部。",
        parameters={
            "to_bottom": {
                "type": "boolean",
                "description": "(可选)是否直接滚动到页面底部，而非向下滚动一屏"
            }
        },
        required=[],
    )
    async def browser_scroll_down(self, to_bottom: Optional[bool] = None) -> ToolResult:
        """向下滚动当前浏览器页面，支持滚动一页或者滚动到底部"""
        return await self.browser.scroll_down(to_bottom)

    @tool(
        name="browser_console_exec",
        description="在浏览器控制台中执行JavaScript代码，当需要执行自定义脚本时使用。",
        parameters={
            "javascript": {
                "type": "string",
                "description": "要执行的JavaScript代码，请注意运行时环境为浏览器控制台。"
            },
        },
        required=["javascript"],
    )
    async def browser_console_exec(self, javascript: str) -> ToolResult:
        """传递js脚本在当前浏览器控制台执行"""
        return await self.browser.console_exec(javascript)

    @tool(
        name="browser_console_view",
        description="查看浏览器控制台输出，用于检查JavaScript日志或调试页面错误。",
        parameters={
            "max_lines": {
                "type": "integer",
                "description": "(可选)返回的最大日志行数。"
            }
        },
        required=[],
    )
    async def browser_console_view(self, max_lines: Optional[int] = None) -> ToolResult:
        """传递浏览的最大行数查看控制台的输出"""
        return await self.browser.console_view(max_lines)
