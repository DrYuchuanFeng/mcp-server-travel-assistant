"""
单次调用 MCP Agent 的示例 (非 CLI 聊天模式)
展示如何将 MCP Agent 封装为函数调用，适合集成到 API 或其他应用中。
"""

import asyncio
import logging

from langchain_mcp_adapters.client import MultiServerMCPClient

from agent_config import Configuration, build_agent, load_tools, reply_text


async def process_user_query(query: str) -> str:
    """处理单个用户请求的函数"""
    cfg = Configuration()
    servers_cfg = Configuration.load_servers()

    # 注意：MultiServerMCPClient 不需要手动关闭，每次工具调用会自行管理连接。
    # 在生产环境中，Client 通常作为全局单例，这里为了演示方便放在函数内。
    mcp_client = MultiServerMCPClient(servers_cfg)
    tools, _ = await load_tools(mcp_client, servers_cfg)

    # 单次无状态调用，不需要 checkpointer
    agent = build_agent(cfg, tools)

    print(f"🚀 开始处理请求: {query}")
    result = await agent.ainvoke({"messages": [{"role": "user", "content": query}]})
    return reply_text(result["messages"][-1])


# 主程序入口
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    response = asyncio.run(process_user_query("北京今天天气如何？"))
    print(f"\n🏁 最终结果:\n{response}")
