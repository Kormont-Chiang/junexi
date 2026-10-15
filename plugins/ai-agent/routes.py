# -*- coding: utf-8 -*-
"""AI agent 插件(R101): /api/ai/agent 工具循环——AI 从"嘴"到"手"。

- 工具来自核心 agent_tools 注册表: 各插件(如 cbdb)注册, 本插件消费, 互不依赖
- deepseek_chat 走延迟 import(请求时主模块已加载完, 无循环导入)
- 禁用时: 端点消失 + 前端开关由本插件 JS 注入, AI 页自然退回纯对话
"""
import json
from flask import Blueprint, request, jsonify

from agent_tools import get_openai_tools, execute_tool, tool_message_content

bp = Blueprint("ai_agent", __name__)

MAX_AGENT_STEPS = 6

AGENT_SYSTEM_PROMPT = (
    "你是「六月息」历史研究工作台的 AI 助手。你已接入 JuneXi 的工具, 可以直接操作它的功能"
    "(人物/官职/地名/亲属/社会关系检索, 以及把人物标到历史地图等, 具体以工具清单为准)。\n"
    "当用户请求可用工具完成时, 优先调工具(可多步组合), 拿到结果后用中文简洁回答, "
    "并顺带说明你在 JuneXi 里打开了什么页面或地图。纯聊天、写作、翻译类问题不用工具, 直接答。\n"
    "铁律: 人物/官职 ID 必须先检索后使用, 绝不凭记忆编造; 一步工具拿不到就换参数重试或如实说明。"
)


@bp.route("/api/ai/agent", methods=["POST"])
def ai_agent():
    """AI 工具循环(agent 模式): 模型自主决定调哪些工具, 最多 MAX_AGENT_STEPS 步"""
    from app import deepseek_chat  # 延迟导入: 插件加载时 app 尚在初始化

    data = request.json or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "message 不能为空"})

    tools = get_openai_tools()
    if not tools:
        return jsonify({"error": "当前没有可用工具(各插件未注册任何 AI 工具)"})

    messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
    # R100: 多轮操作对话——前端带最近 10 轮简史(user/assistant 才收, 防注入其他角色)
    for h in (data.get("history") or [])[-10:]:
        if not isinstance(h, dict):
            continue
        role = h.get("role")
        content = str(h.get("content", ""))[:2000]
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})

    steps = []
    actions = []
    final = ""
    model_id = data.get("model")

    for _step in range(MAX_AGENT_STEPS):
        result = deepseek_chat(messages, model_id=model_id, tools=tools)
        if not isinstance(result, dict) or "choices" not in result:
            err = result.get("error") if isinstance(result, dict) else "模型服务不可用"
            return jsonify({"error": err, "steps": steps, "actions": actions})
        msg = result["choices"][0]["message"]
        tool_calls = msg.get("tool_calls") or []
        content = msg.get("content") or ""
        if not tool_calls:
            final = content
            break
        messages.append(msg)
        for tc in tool_calls:
            fn = tc.get("function") or {}
            fname = fn.get("name", "")
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except Exception:
                args = {}
            tresult, action = execute_tool(fname, args)
            ok = not (isinstance(tresult, dict) and tresult.get("error"))
            steps.append({"tool": fname, "args": args, "ok": ok})
            if action:
                actions.append(action)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "name": fname,
                "content": tool_message_content(tresult),
            })
    else:
        return jsonify({"response": "(已达最大步数, 请缩小范围重试)", "steps": steps, "actions": actions})

    return jsonify({"response": final, "steps": steps, "actions": actions})
