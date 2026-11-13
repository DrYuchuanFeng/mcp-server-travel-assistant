"""
MCP Agent 公共配置
------------------
api_server.py / client.py / client_simple.py 共用：
1. 从 .env 读取 OPENAI_API_KEY / MODEL
2. 读取 servers_config.json，并把 ${变量名} 替换成 .env 中的值
3. 逐个连接 MCP 服务器，单个服务器失败不影响其他工具
4. 用 OpenAI 模型构造 LangGraph Agent
"""

import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode, create_react_agent

from maps_args import MAPS_TOOLS, sanitize_maps_args

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL = "gpt-6-luna"
DEFAULT_PROMPT = "你是一个智能助手。"

load_dotenv(BASE_DIR / ".env")

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
# 模型偶尔输出的内部引用标记，例如 citeturn0search0（可能夹带私有区字符）
_CITATION_PATTERN = re.compile(r"\s*[-]*cite[-]*(?:turn\d+[a-z]+\d+[-]*)+")


def _expand_env(value: Any) -> Any:
    """递归替换配置中的 ${变量名}；变量缺失时抛出 KeyError。"""
    if isinstance(value, str):
        return _ENV_PATTERN.sub(lambda m: _require_env(m.group(1)), value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise KeyError(name)
    return value


def _prepare_stdio(server: dict[str, Any]) -> dict[str, Any]:
    """让本地 MCP 服务器使用当前虚拟环境的 Python，且不依赖启动目录。"""
    if server.get("command") == "python":
        server["command"] = sys.executable
    server["args"] = [
        str(BASE_DIR / arg) if arg.endswith(".py") and not Path(arg).is_absolute() else arg
        for arg in server.get("args", [])
    ]
    server.setdefault("cwd", str(BASE_DIR))
    return server


class Configuration:
    """读取 .env 与 servers_config.json"""

    def __init__(self) -> None:
        self.api_key: str = os.getenv("OPENAI_API_KEY") or ""
        self.model: str = os.getenv("MODEL") or DEFAULT_MODEL
        if not self.api_key:
            raise ValueError("❌ 未找到 OPENAI_API_KEY，请在 .env 中配置")

    @staticmethod
    def load_servers(file_path: Path = BASE_DIR / "servers_config.json") -> dict[str, Any]:
        """返回可直接交给 MultiServerMCPClient 的配置；缺少 Key 的服务器会被跳过。"""
        with open(file_path, "r", encoding="utf-8") as f:
            raw_servers = json.load(f).get("mcpServers", {})

        servers: dict[str, Any] = {}
        for name, raw in raw_servers.items():
            try:
                server = _expand_env(raw)
            except KeyError as missing:
                logging.warning("⚠️ 跳过 MCP 服务器 %s：.env 中缺少 %s", name, missing)
                continue
            servers[name] = _prepare_stdio(server) if server.get("transport") == "stdio" else server
        return servers


async def load_tools(
    client: MultiServerMCPClient, servers: dict[str, Any]
) -> tuple[list[Any], dict[str, list[str]]]:
    """逐个加载工具，返回 (全部工具, {已连接的服务器名: 工具名列表})。"""
    tools: list[Any] = []
    connected: dict[str, list[str]] = {}
    for name in servers:
        try:
            server_tools = await client.get_tools(server_name=name)
        except Exception as exc:
            logging.error("❌ MCP 服务器 %s 连接失败: %s", name, exc)
            continue
        tools.extend(server_tools)
        connected[name] = [tool.name for tool in server_tools]
        logging.info("✅ %s: %s", name, connected[name])
    return tools, connected


def _tool_error_message(exc: Exception) -> str:
    """把工具异常交还给模型，让它修正参数重试，而不是中断整轮对话。"""
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    logging.warning("⚠️ 工具调用失败: %s", exc)
    return f"工具调用失败：{exc}。请检查参数后重试；如果仍然失败，请如实告诉用户。"


async def _clean_maps_call(request: Any, execute: Any) -> Any:
    """调用 Google 地图工具前先规范参数。"""
    call = request.tool_call
    if call["name"] in MAPS_TOOLS:
        args = sanitize_maps_args(call["name"], call["args"])
        request = request.override(tool_call={**call, "args": args})
    return await execute(request)


def build_agent(cfg: Configuration, tools: list[Any], checkpointer: Any = None) -> Any:
    """用 OpenAI 模型和 MCP 工具构造 Agent。"""
    prompt_path = BASE_DIR / "agent_prompts.txt"
    prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else DEFAULT_PROMPT

    def prompt_with_date(state: dict[str, Any]) -> list[Any]:
        today = datetime.now().astimezone().strftime("%Y-%m-%d %A")
        return [SystemMessage(content=f"{prompt}\n\n今天的日期：{today}"), *state["messages"]]

    model = ChatOpenAI(model=cfg.model, api_key=cfg.api_key, streaming=False)
    tool_node = ToolNode(tools, handle_tool_errors=_tool_error_message, awrap_tool_call=_clean_maps_call)
    return create_react_agent(model=model, tools=tool_node, prompt=prompt_with_date, checkpointer=checkpointer)


def reply_text(message: Any) -> str:
    """取出模型回复的纯文本，并去掉内部引用标记。"""
    return _CITATION_PATTERN.sub("", str(message.text)).strip()
