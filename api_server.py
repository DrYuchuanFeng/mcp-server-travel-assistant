import logging
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel

from agent_config import Configuration, build_agent, load_tools, reply_text

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# 全局变量存储 agent 和运行状态
agent = None
model_name = ""
connected_servers: dict[str, list[str]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 生命周期管理：启动时连接 MCP 并创建 Agent"""
    global agent, model_name, connected_servers

    logging.info("🚀 正在启动 MCP Agent API...")

    cfg = Configuration()
    servers_cfg = Configuration.load_servers()
    mcp_client = MultiServerMCPClient(servers_cfg)
    tools, connected_servers = await load_tools(mcp_client, servers_cfg)
    logging.info("✅ 已加载 %d 个 MCP 工具", len(tools))

    model_name = cfg.model
    agent = build_agent(cfg, tools, checkpointer=InMemorySaver())

    yield


app = FastAPI(lifespan=lifespan)

# 允许跨域（方便前端调试）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "1"


class ChatResponse(BaseModel):
    content: str
    status: str = "success"
    error: str | None = None


class StatusResponse(BaseModel):
    model: str
    servers: dict[str, list[str]]


@app.get("/status", response_model=StatusResponse)
async def status_endpoint():
    """返回当前模型和已连接的 MCP 服务器，供前端显示"""
    return StatusResponse(model=model_name, servers=connected_servers)


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """普通聊天接口（非流式），返回完整结果"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent 未初始化")

    run_config = {"configurable": {"thread_id": request.thread_id}}

    try:
        logging.info("收到请求: %s", request.message)

        # 直接调用 invoke，等待完整结果
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=request.message)]},
            run_config,
        )

        if result.get("messages"):
            return ChatResponse(content=reply_text(result["messages"][-1]))
        return ChatResponse(content="未获取到回复", status="empty")

    except Exception as e:
        logging.error("处理出错: %s", traceback.format_exc())
        # 返回错误信息给前端
        return ChatResponse(content="", status="error", error=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
