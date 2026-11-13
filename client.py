"""
多服务器 MCP + LangChain Agent 示例
---------------------------------
1. 读取 .env 中的 OPENAI_API_KEY / MODEL
2. 读取 servers_config.json 中的 MCP 服务器信息
3. 启动 MCP 服务器（支持多个）
4. 将所有工具注入 LangGraph Agent，由大模型自动选择并调用
yong7623822.Yo
"""

import asyncio
import logging

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.memory import InMemorySaver

from agent_config import Configuration, build_agent, load_tools, reply_text

# 设置记忆存储
checkpointer = InMemorySaver()

# 设置对话配置
config = {
    "configurable": {
        "thread_id": "1"
    }
}

# ────────────────────────────
# 主逻辑
# ────────────────────────────
async def run_chat_loop() -> None:
    """启动 MCP-Agent 聊天循环"""
    cfg = Configuration()
    servers_cfg = Configuration.load_servers()

    # 1️ 连接多台 MCP 服务器，单台失败不影响其他工具
    mcp_client = MultiServerMCPClient(servers_cfg)
    tools, _ = await load_tools(mcp_client, servers_cfg)
    logging.info(f"✅ 已加载 {len(tools)} 个 MCP 工具： {[t.name for t in tools]}")

    # 2️ 用 OpenAI 模型构造 LangGraph Agent
    agent = build_agent(cfg, tools, checkpointer=checkpointer)

    # 3 CLI 聊天
    print("\n🤖 MCP Agent 已启动，输入 'quit' 退出")
    while True:
        user_input = input("\n你: ").strip()
        if user_input.lower() == "quit":
            break
        try:
            result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": user_input}]},
            config
        )
            print(f"\nAI: {reply_text(result['messages'][-1])}")
        except Exception as exc:
            print(f"\n⚠️  出错: {exc}")

    print("👋 Bye!")

# ────────────────────────────
# 入口
# ────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    asyncio.run(run_chat_loop())
