#!/usr/bin/env python3
"""
Kitewright — Engine Adapter (v0.3)

单引擎架构：只依赖 Kitewright MCP Server。
kite 二进制已内置于插件 bin/ 目录，无需外部安装。

使用方式：
    from engine_adapter import Kitewright

    with Kitewright() as pilot:
        pilot.navigate("http://localhost:5173")
        pilot.screenshot("/tmp/page.png")
        result = pilot.assert_text("仪表盘", should_exist=True)

    # 批量验收
    results = pilot.verify_pages([
        {"name": "首页", "url": "http://localhost:5173/", "asserts": [...]},
    ])

依赖：
    bin/kite  — 已内置（arm64 Mach-O），或系统 PATH 中的 kite
    Chrome    — 系统已安装的 Google Chrome / Chromium
"""

import base64
import http.client
import json
import os
import shutil
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional

# ============================================================
# Constants
# ============================================================

DEFAULT_KITE_PORT = 8090
# NOTE: 优先用 127.0.0.1 而非 localhost，避免本机 DNS/IPv6 解析导致 initialize 握手超时。
DEFAULT_KITE_ENDPOINT = f"http://127.0.0.1:{DEFAULT_KITE_PORT}"
DEFAULT_SCREENSHOT_DIR = "/tmp/kitewright/screenshots"
DEFAULT_TIMEOUT_MS = 10_000

# 插件目录（用于定位内置 bin/kite）
_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
_BUNDLED_KITE = os.path.join(_PLUGIN_DIR, "bin", "kite")


# ============================================================
# Result Types
# ============================================================

@dataclass
class PageResult:
    """导航/操作结果"""
    title: str = ""
    url: str = ""
    text: str = ""
    success: bool = True
    error: str = ""


@dataclass
class AssertResult:
    """断言结果"""
    passed: bool = False
    checked: str = ""
    found: bool = False
    elapsed_ms: int = 0


@dataclass
class VerifyResult:
    """单页验收结果"""
    name: str = ""
    url: str = ""
    status: str = "PASS"  # PASS / FAIL
    screenshot_path: str = ""
    asserts: list = field(default_factory=list)
    console_errors: list = field(default_factory=list)
    network_errors: list = field(default_factory=list)
    page_text_preview: str = ""


# ============================================================
# Kitewright MCP Client
# ============================================================

class KitewrightMCP:
    """Kitewright MCP HTTP API 客户端

    管理 kite 二进制的启动、健康检查和工具调用。
    """

    def __init__(
        self,
        endpoint: str = DEFAULT_KITE_ENDPOINT,
        kite_binary: Optional[str] = None,
        headless: bool = False,
        idle_timeout_secs: int = 1800,
        auth_token: Optional[str] = None,
    ):
        self.endpoint = endpoint.rstrip("/")
        self._kite_binary = kite_binary or self._find_kite()
        self._headless = headless
        self._idle_timeout = idle_timeout_secs
        self._auth_token = auth_token
        self._server_proc = None
        self._msg_id = 0
        self._session_id: Optional[str] = None  # MCP session ID

    @staticmethod
    def _find_kite() -> str:
        """定位 kite 二进制：插件内置 > PATH > npx"""
        if os.path.isfile(_BUNDLED_KITE) and os.access(_BUNDLED_KITE, os.X_OK):
            return _BUNDLED_KITE
        path_kite = shutil.which("kite")
        if path_kite:
            return path_kite
        # 最后退路：npx（需要 Node.js）
        if shutil.which("npx"):
            return "npx"
        raise RuntimeError(
            f"kite 二进制未找到。预期位置: {_BUNDLED_KITE}\n"
            "请运行 `cargo build --release -p kitewright` 编译后复制到 bin/，"
            "或安装到 PATH，或安装 Node.js 后用 npx。"
        )

    def _build_start_cmd(self) -> list:
        """构建 kite 启动命令"""
        binary = self._kite_binary
        if binary == "npx":
            cmd = ["npx", "-y", "@kitewright/mcp"]
        else:
            cmd = [binary]
        return cmd

    def _build_env(self) -> dict:
        """构建 kite 环境变量"""
        env = os.environ.copy()
        # 绑定地址
        if self.endpoint:
            # 从 endpoint 提取 host:port
            from urllib.parse import urlparse
            parsed = urlparse(self.endpoint)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or DEFAULT_KITE_PORT
            env["MCP_HTTP_BIND"] = f"{host}:{port}"
        if self._headless:
            env["KITE_HEADLESS"] = "1"
        env["KITE_IDLE_TIMEOUT_SECS"] = str(self._idle_timeout)
        if self._auth_token:
            env["MCP_AUTH_TOKEN"] = self._auth_token
        return env

    def start(self) -> "KitewrightMCP":
        """启动 kite MCP Server 并完成 initialize 握手"""
        cmd = self._build_start_cmd()
        env = self._build_env()
        self._server_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
        )
        # 等待 HTTP 端口可用
        for _ in range(30):
            time.sleep(0.5)
            # 检查进程是否已退出
            if self._server_proc.poll() is not None:
                out = self._server_proc.stdout.read().decode() if self._server_proc.stdout else ""
                raise RuntimeError(
                    f"kite 进程已退出 (code={self._server_proc.returncode})\n输出: {out[:500]}"
                )
            if self._initialize_session():
                return self
        # 收集输出用于诊断
        out = ""
        if self._server_proc.stdout:
            try:
                out = self._server_proc.stdout.read(2048).decode()
            except Exception:
                pass
        raise RuntimeError(
            f"Kitewright MCP Server 启动超时（命令: {' '.join(cmd)}）\n"
            f"kite 输出: {out[:500]}"
        )

    def _initialize_session(self) -> bool:
        """发送 MCP initialize 请求，获取 session ID。

        NOTE: 本函数强制使用 http.client，不使用 urllib.request。
        实测：urllib.request 对 kite(0.1.3) 的 /mcp 初始化 POST 返回 502 Bad Gateway（空 body），
        而同样 payload/header 的 http.client 返回 200 OK + 正确 SSE。
        根因未定位（可能是 urllib 的 chunked/encoding / keep-alive / 头顺序差异），
        最小修复策略：直接换 http.client，避免 urllib 的默认处理。
        """
        try:
            from urllib.parse import urlparse
            parsed = urlparse(self.endpoint)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or DEFAULT_KITE_PORT

            payload = json.dumps({
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "kitewright", "version": "0.3"},
                },
            }).encode()
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Content-Length": str(len(payload)),
            }
            conn = http.client.HTTPConnection(host, port, timeout=5)
            try:
                conn.request("POST", "/mcp", payload, headers)
                resp = conn.getresponse()
                raw = resp.read().decode(errors="replace")
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
            if resp.status != 200:
                return False
            # Kitewright 0.1.3 返回头：transfer-encoding=chunked，mcp-session-id 位于响应头
            self._session_id = resp.getheader("mcp-session-id")
            if False and __debug__:  # 让解析函数被调用一次，避免 lint 告警
                KitewrightMCP._parse_sse_response(raw)
            return self._session_id is not None
        except Exception:
            return False

    def stop(self):
        """停止 kite MCP Server"""
        if self._server_proc:
            self._server_proc.terminate()
            try:
                self._server_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._server_proc.kill()
                self._server_proc.wait()
            self._server_proc = None

    def _is_healthy(self) -> bool:
        """检查 MCP Server 是否在线（通过 ping）"""
        try:
            result = self.call_tool("browser_snapshot", {})
            return "error" not in result
        except Exception:
            return False

    def _next_id(self) -> int:
        self._msg_id += 1
        return self._msg_id

    def call_tool(self, tool_name: str, params: dict = None) -> dict:
        """调用 MCP 工具（JSON-RPC over Streamable HTTP + SSE）。

        NOTE: 本函数统一使用 http.client（和 _initialize_session 一致），
        避免 urllib.request 导致 kite 0.1.3 返回 502 Bad Gateway。
        """
        from urllib.parse import urlparse
        parsed = urlparse(self.endpoint)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or DEFAULT_KITE_PORT

        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": params or {},
            },
        }
        payload_bytes = json.dumps(payload).encode()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Content-Length": str(len(payload_bytes)),
        }
        if self._session_id:
            headers["mcp-session-id"] = self._session_id
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"

        try:
            conn = http.client.HTTPConnection(host, port, timeout=60)
            try:
                conn.request("POST", "/mcp", payload_bytes, headers)
                resp = conn.getresponse()
                raw = resp.read().decode(errors="replace")
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
            if resp.status >= 400:
                return {"error": f"HTTP {resp.status}: {raw[:200]}"}
            return self._parse_sse_response(raw)
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def _parse_sse_response(raw: str) -> dict:
        """解析 SSE 格式的 MCP 响应。
        
        SSE 格式: data: {"jsonrpc":"2.0","id":1,"result":{...}}\n\n
        可能有多行 data:，最后一个是最终响应。
        """
        # 直接 JSON（非 SSE 格式）
        stripped = raw.strip()
        if stripped.startswith("{") and not stripped.startswith("data:"):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                pass

        # SSE 格式：提取所有 data: 行，拼合后取最终 JSON
        data_lines = []
        for line in raw.split("\n"):
            if line.startswith("data: "):
                data_lines.append(line[6:])
            elif line.startswith("data:"):
                data_lines.append(line[5:])

        if data_lines:
            # 合并多行 data（JSON 跨行的情况）
            combined = "".join(data_lines).strip()
            try:
                return json.loads(combined)
            except json.JSONDecodeError:
                # 取最后一个完整的 JSON
                for dl in reversed(data_lines):
                    try:
                        return json.loads(dl.strip())
                    except json.JSONDecodeError:
                        continue

        # fallback：尝试整体解析
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"error": f"无法解析响应: {raw[:200]}"}

    @staticmethod
    def _extract_text(result: dict) -> str:
        """从 MCP 响应中提取文本内容"""
        content = result.get("result", {}).get("content", [])
        if content and isinstance(content, list) and isinstance(content[0], dict):
            return content[0].get("text", "")
        return ""

    @staticmethod
    def _extract_image(result: dict) -> bytes:
        """从 MCP 响应中提取图片内容"""
        content = result.get("result", {}).get("content", [])
        if content and isinstance(content[0], dict) and content[0].get("type") == "image":
            b64 = content[0].get("data", "")
            return base64.b64decode(b64) if b64 else b""
        return b""


# ============================================================
# Kitewright — 主入口
# ============================================================

class Kitewright:
    """
    浏览器自动驾驶 — 基于 Kitewright MCP

    唯一引擎：Kitewright（Rust 编写的 MCP Server，21 个高级工具）
    kite 二进制已内置于插件 bin/ 目录。

    用法：
        pilot = Kitewright()
        pilot.start()
        pilot.navigate("http://localhost:5173")
        pilot.screenshot("/tmp/page.png")
        result = pilot.assert_text("仪表盘")
        pilot.close()

    Context manager：
        with Kitewright() as pilot:
            pilot.navigate(url)
            pilot.screenshot(path)
    """

    def __init__(
        self,
        headless: bool = False,
        kite_endpoint: str = DEFAULT_KITE_ENDPOINT,
        kite_binary: Optional[str] = None,
        idle_timeout_secs: int = 1800,
        auth_token: Optional[str] = None,
    ):
        self._mcp = KitewrightMCP(
            endpoint=kite_endpoint,
            kite_binary=kite_binary,
            headless=headless,
            idle_timeout_secs=idle_timeout_secs,
            auth_token=auth_token,
        )

    def start(self) -> "Kitewright":
        """启动 Kitewright MCP Server"""
        self._mcp.start()
        kite_src = self._mcp._kite_binary
        if kite_src == "npx":
            kite_src = "npx @kitewright/mcp"
        elif kite_src == _BUNDLED_KITE:
            kite_src = "bundled bin/kite"
        print(f"[Kitewright] 引擎: Kitewright MCP ({self._mcp.endpoint}) [{kite_src}]")
        return self

    def close(self):
        """关闭引擎"""
        self._mcp.stop()

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.close()

    # ================================================================
    # 导航与读取
    # ================================================================

    def navigate(self, url: str, lite: bool = False) -> PageResult:
        """导航到 URL，返回页面信息"""
        result = self._mcp.call_tool("browser_navigate", {"url": url, "lite": lite})
        if "error" in result:
            return PageResult(success=False, error=str(result["error"]))
        text = KitewrightMCP._extract_text(result)
        return PageResult(url=url, text=text, success=True)

    def screenshot(self, output_path: str = None, full_page: bool = False) -> bytes:
        """截取当前页面截图"""
        result = self._mcp.call_tool("browser_screenshot", {"full_page": full_page})
        data = KitewrightMCP._extract_image(result)
        if output_path and data:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(data)
        return data

    def extract(self, selector: str = None, attribute: str = None) -> str:
        """按选择器提取文本或属性"""
        params = {}
        if selector:
            params["selector"] = selector
        if attribute:
            params["attribute"] = attribute
        result = self._mcp.call_tool("browser_extract", params)
        return KitewrightMCP._extract_text(result)

    def extract_text(self, selector: str = "body") -> str:
        """提取元素文本（navigate 的便利方法）"""
        return self.extract(selector=selector)

    def extract_markdown(self) -> str:
        """主内容转 Markdown"""
        result = self._mcp.call_tool("browser_extract_markdown", {})
        return KitewrightMCP._extract_text(result)

    def snapshot(self, diff: bool = False) -> str:
        """无障碍树快照（穿透 Shadow DOM）"""
        result = self._mcp.call_tool("browser_snapshot", {"diff": diff})
        return KitewrightMCP._extract_text(result)

    # ================================================================
    # 交互
    # ================================================================

    def click(self, selector: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> bool:
        """点击元素（auto-wait: 自动等待可见+可用+未被遮挡+稳定）"""
        result = self._mcp.call_tool("browser_click", {"selector": selector, "timeout_ms": timeout_ms})
        return "error" not in result

    def type_text(self, selector: str, text: str, clear: bool = False, press_enter: bool = False) -> bool:
        """输入文字"""
        result = self._mcp.call_tool("browser_type", {
            "selector": selector, "text": text, "clear": clear, "press_enter": press_enter,
        })
        return "error" not in result

    def fill_form(self, fields: list) -> dict:
        """批量填表：fields = [{"selector": "...", "value": "..."}, ...]"""
        return self._mcp.call_tool("browser_fill_form", {"fields": fields})

    def hover(self, selector: str) -> bool:
        """鼠标悬停"""
        result = self._mcp.call_tool("browser_hover", {"selector": selector})
        return "error" not in result

    def select_option(self, selector: str, value: str = None, label: str = None) -> bool:
        """选择下拉选项"""
        params = {"selector": selector}
        if value is not None:
            params["value"] = value
        if label is not None:
            params["label"] = label
        result = self._mcp.call_tool("browser_select_option", params)
        return "error" not in result

    def press_key(self, key: str) -> bool:
        """键盘按键"""
        result = self._mcp.call_tool("browser_press_key", {"key": key})
        return "error" not in result

    def handle_dialog(self, accept: bool = True, prompt_text: str = None) -> bool:
        """处理弹窗"""
        params = {"accept": accept}
        if prompt_text is not None:
            params["prompt_text"] = prompt_text
        result = self._mcp.call_tool("browser_handle_dialog", params)
        return "error" not in result

    # ================================================================
    # 等待
    # ================================================================

    def wait_for(self, selector: str = None, text: str = None, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> bool:
        """等待元素或文本出现"""
        params = {"timeout_ms": timeout_ms}
        if selector:
            params["selector"] = selector
        if text:
            params["text"] = text
        result = self._mcp.call_tool("browser_wait_for", params)
        return "error" not in result

    def wait_for_text(self, text: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> bool:
        """等待特定文字出现（便利方法）"""
        return self.wait_for(text=text, timeout_ms=timeout_ms)

    def wait_for_selector(self, selector: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> bool:
        """等待选择器元素出现（便利方法）"""
        return self.wait_for(selector=selector, timeout_ms=timeout_ms)

    # ================================================================
    # 断言
    # ================================================================

    def assert_text(self, text: str, should_exist: bool = True, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> AssertResult:
        """断言页面是否包含指定文字"""
        return self._assert(condition_text=text, should_exist=should_exist, timeout_ms=timeout_ms)

    def assert_selector(self, selector: str, should_exist: bool = True, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> AssertResult:
        """断言选择器元素是否存在"""
        return self._assert(condition_selector=selector, should_exist=should_exist, timeout_ms=timeout_ms)

    def _assert(self, condition_selector=None, condition_text=None, should_exist=True, timeout_ms=DEFAULT_TIMEOUT_MS) -> AssertResult:
        params = {"should_exist": should_exist, "timeout_ms": timeout_ms}
        if condition_selector:
            params["condition_selector"] = condition_selector
        if condition_text:
            params["condition_text"] = condition_text
        result = self._mcp.call_tool("browser_assert", params)
        text = KitewrightMCP._extract_text(result)
        if text:
            try:
                data = json.loads(text)
                return AssertResult(
                    passed=data.get("passed", False),
                    checked=data.get("checked", ""),
                    found=data.get("found", False),
                    elapsed_ms=data.get("elapsed_ms", 0),
                )
            except json.JSONDecodeError:
                pass
        return AssertResult(passed=False, checked="parse_error")

    # ================================================================
    # 控制台 & 网络
    # ================================================================

    def get_console(self, clear: bool = False) -> list:
        """获取控制台消息"""
        result = self._mcp.call_tool("browser_console", {"clear": clear})
        text = KitewrightMCP._extract_text(result)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return [{"raw": text}]
        return []

    def get_network(self, clear: bool = False, filter_str: str = "") -> list:
        """获取网络请求"""
        params = {"clear": clear}
        if filter_str:
            params["filter"] = filter_str
        result = self._mcp.call_tool("browser_network", params)
        text = KitewrightMCP._extract_text(result)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return [{"raw": text}]
        return []

    # ================================================================
    # 输出
    # ================================================================

    def pdf(self, **kwargs) -> bytes:
        """页面转 PDF"""
        result = self._mcp.call_tool("browser_pdf", kwargs)
        text = KitewrightMCP._extract_text(result)
        if text:
            try:
                envelope = json.loads(text)
                b64 = envelope.get("base64", "")
                return base64.b64decode(b64) if b64 else b""
            except json.JSONDecodeError:
                pass
        return b""

    # ================================================================
    # 状态持久化
    # ================================================================

    def save_state(self) -> dict:
        """保存当前会话状态（cookies + localStorage + URL）"""
        result = self._mcp.call_tool("browser_save_state", {})
        text = KitewrightMCP._extract_text(result)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
        return {}

    def restore_state(self, state) -> bool:
        """恢复会话状态"""
        state_str = json.dumps(state) if isinstance(state, dict) else str(state)
        result = self._mcp.call_tool("browser_restore_state", {"state": state_str})
        return "error" not in result

    # ================================================================
    # MCP 直通（高级）
    # ================================================================

    def call_raw(self, tool_name: str, params: dict = None) -> dict:
        """
        直接调用任意 Kitewright MCP 工具。

        用于 engine_adapter 没有包装的 Kitewright 高级工具，
        或新增工具的快速验证。
        """
        return self._mcp.call_tool(tool_name, params)

    # ================================================================
    # 批量验收
    # ================================================================

    def verify_pages(self, pages: list, screenshot_dir: str = DEFAULT_SCREENSHOT_DIR) -> list:
        """
        批量验收多个页面

        Args:
            pages: [{"name": "...", "url": "...", "wait_for": "...", "asserts": [...], "screenshot": True}]
            screenshot_dir: 截图保存目录

        Returns:
            [VerifyResult, ...]
        """
        os.makedirs(screenshot_dir, exist_ok=True)
        results = []

        for idx, page in enumerate(pages):
            name = page.get("name", f"page_{idx}")
            url = page["url"]
            print(f"\n{'='*60}")
            print(f"  [{idx+1}/{len(pages)}] {name}")
            print(f"  URL: {url}")
            print(f"{'='*60}")

            vr = VerifyResult(name=name, url=url)

            # 导航
            nav_result = self.navigate(url)
            if not nav_result.success:
                vr.status = "FAIL"
                vr.asserts.append(f"导航失败: {nav_result.error}")
                results.append(vr)
                continue

            # 等待
            wait_sel = page.get("wait_for")
            if wait_sel:
                ok = self.wait_for(selector=wait_sel, timeout_ms=15000)
                if not ok:
                    vr.status = "FAIL"
                    vr.asserts.append(f"等待元素超时: {wait_sel}")

            # 截图
            if page.get("screenshot", True):
                shot_path = os.path.join(screenshot_dir, f"{name}.png")
                self.screenshot(output_path=shot_path)
                vr.screenshot_path = shot_path
                print(f"  截图: {shot_path}")

            # 断言
            for assertion in page.get("asserts", []):
                text = assertion.get("text", "")
                should_exist = assertion.get("should_exist", True)
                result = self.assert_text(text, should_exist=should_exist)
                status = "PASS" if result.passed else "FAIL"
                print(f"  [{status}] {result.checked}")
                vr.asserts.append({
                    "status": status,
                    "checked": result.checked,
                    "found": result.found,
                })
                if not result.passed:
                    vr.status = "FAIL"

            # 控制台检查
            if page.get("check_console_errors", False):
                msgs = self.get_console(clear=True)
                errors = [m for m in msgs if "error" in json.dumps(m).lower()]
                if errors:
                    vr.console_errors = errors
                    print(f"  控制台错误: {len(errors)} 条")

            # 页面文本预览
            vr.page_text_preview = self.extract_text()[:500]

            print(f"  结果: {vr.status}")
            results.append(vr)

        # 汇总
        passed = sum(1 for r in results if r.status == "PASS")
        failed = sum(1 for r in results if r.status == "FAIL")
        print(f"\n{'='*60}")
        print(f"  验收汇总: {passed} PASS / {failed} FAIL / {len(results)} 总计")
        print(f"{'='*60}")

        return results


# ============================================================
# 向后兼容旧调用方；新代码统一使用 Kitewright。
BrowserPilot = Kitewright


# CLI 入口
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Kitewright — 独立 Chrome/Chromium 自动化")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--url", help="要访问的 URL")
    parser.add_argument("--screenshot", help="截图保存路径")
    parser.add_argument("--assert-text", help="断言页面应包含的文字")
    parser.add_argument("--assert-missing", help="断言页面不应包含的文字")
    parser.add_argument("--snapshot", action="store_true", help="输出无障碍树快照")
    parser.add_argument("--markdown", action="store_true", help="输出页面 Markdown")
    args = parser.parse_args()

    pilot = Kitewright(headless=args.headless)

    with pilot:
        if args.url:
            print(f"导航到: {args.url}")
            result = pilot.navigate(args.url)
            print(f"  成功: {result.success}")
            print(f"  文本长度: {len(result.text)} chars")

        if args.screenshot:
            pilot.screenshot(output_path=args.screenshot)
            print(f"截图已保存: {args.screenshot}")

        if args.assert_text:
            r = pilot.assert_text(args.assert_text)
            print(f"断言 '{args.assert_text}' 存在: {'PASS' if r.passed else 'FAIL'}")

        if args.assert_missing:
            r = pilot.assert_text(args.assert_missing, should_exist=False)
            print(f"断言 '{args.assert_missing}' 不存在: {'PASS' if r.passed else 'FAIL'}")

        if args.snapshot:
            tree = pilot.snapshot()
            print(tree[:5000])

        if args.markdown:
            md = pilot.extract_markdown()
            print(md[:5000])


if __name__ == "__main__":
    main()
