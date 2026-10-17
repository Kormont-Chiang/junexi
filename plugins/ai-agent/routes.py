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
    "(人物/官职/地名/亲属/社会关系检索、Zotero 书库、Obsidian 笔记、地图等, 具体以工具清单为准)。\n"
    "当用户请求可用工具完成时, 优先调工具(可多步组合), 拿到结果后用中文简洁回答, "
    "并顺带说明你在 JuneXi 里打开了什么页面或地图。纯聊天、写作、翻译类问题不用工具, 直接答。\n"
    "铁律: 人物/官职 ID 必须先检索后使用, 绝不凭记忆编造; 一步工具拿不到就换参数重试或如实说明。\n"
    "效率纪律: 整理笔记/写总结时优先用已有工具结果, 补查详情每次至多 2 人, 别把调用浪费在逐人详情上; "
    "工具调用总数有限, 拿全所需材料就动手写, 不要恋战。"
)

MAX_TOOL_CALLS = 10  # 模型一轮可并行发多个 tool_call, 必须按调用总数兜底(R103b)


@bp.route("/api/ai/agent", methods=["POST"])
def ai_agent():
    """AI 工具循环(agent 模式): 模型自主决定调哪些工具, 最多 MAX_AGENT_STEPS 步"""
    from app import deepseek_chat  # 延迟导入: 插件加载时 app 尚在初始化
    from datetime import date as _date

    data = request.json or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "message 不能为空"})

    tools = get_openai_tools()
    if not tools:
        return jsonify({"error": "当前没有可用工具(各插件未注册任何 AI 工具)"})

    # 带上今天日期: 模型不知道当前时间, "标题带日期"类请求否则瞎编
    system_prompt = "今天是 %s。\n%s" % (_date.today().isoformat(), AGENT_SYSTEM_PROMPT)
    messages = [{"role": "system", "content": system_prompt}]
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
    total_calls = 0
    capped = False
    # R115: 用户可在插件设置里调步数/工具数上限
    max_steps, max_tool_calls = MAX_AGENT_STEPS, MAX_TOOL_CALLS
    try:
        import plugin_loader as _pl
        _cfg = _pl.get_plugin_config("ai-agent")
        max_steps = max(2, min(int(_cfg.get("max_steps") or MAX_AGENT_STEPS), 20))
        max_tool_calls = max(2, min(int(_cfg.get("max_tool_calls") or MAX_TOOL_CALLS), 30))
    except Exception:
        pass

    for _step in range(max_steps):
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
            if total_calls >= max_tool_calls:
                capped = True
                break
            total_calls += 1
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
        if capped:
            break

    if capped or not final:
        # R103b: 工具数/步数耗尽时不用工具收个尾, 基于已有结果作答, 不甩裸失败
        try:
            summary = deepseek_chat(
                messages + [{"role": "system", "content":
                             "工具调用已达上限。请基于已获得的结果直接作答(中文简洁), 不要再请求工具。"}],
                model_id=model_id)
            if isinstance(summary, dict) and "choices" in summary:
                final = summary["choices"][0]["message"].get("content") or final
        except Exception:
            pass
        if capped and final:
            final += "\n\n(已达工具调用上限, 未完成的计划已略去)"

    return jsonify({"response": final or "(已达工具调用上限, 请缩小范围重试)",
                    "steps": steps, "actions": actions})
