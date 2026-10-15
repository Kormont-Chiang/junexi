# -*- coding: utf-8 -*-
"""AI 工具注册表——六月息 AI 助手的"手"。

- 核心(app.py)与插件(如 cbdb)都可注册工具: @tool(...) 声明 schema + 执行函数 + 可选前端动作模板
- app.py 的 /api/ai/agent 循环消费本注册表; 插件 routes.py 在模块底部注册(经 plugin_loader 导入即生效)
- 动作模板: 工具执行成功(返回无 error)后, 按模板生成前端动作; 值 "{参数名}" 从工具入参取值, 其余原样传递
"""
import json as _json
import re as _re

_REGISTRY = {}


def to_int_list(v, limit=500):
    """模型参数归一化: [1762]/"1762"/"1762,1493"/"1762 1493" → [1762, 1493]。
    R99c 事故教训: 模型 array 参数可能序列化成字符串, 逐字符迭代会把 "1762" 拆成 [1,7,6,2]。"""
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        raw = list(v)
    else:
        raw = _re.split(r"[,，、;；\s]+", str(v).strip())
    out = []
    for x in raw:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            continue
    return out[:limit]


def tool(name, description, params=None, action=None):
    """装饰器: 注册 AI 工具。
    name: 工具名(英文, function-calling 用)
    description: 给模型看的能力描述(中文, 说清何时用/返回什么)
    params: JSON Schema (object), 参数定义
    action: dict|None, 执行成功后下发前端的动作模板
    """
    def wrap(fn):
        _REGISTRY[name] = {
            "name": name,
            "description": description,
            "params": params or {"type": "object", "properties": {}},
            "action": action,
            "func": fn,
        }
        return fn
    return wrap


def get_openai_tools():
    """转 OpenAI function-calling 的 tools 数组"""
    out = []
    for t in _REGISTRY.values():
        out.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["params"],
            }
        })
    return out


def execute_tool(name, args):
    """执行工具 → (给模型看的结果, 给前端的动作|None)"""
    t = _REGISTRY.get(name)
    if not t:
        return {"error": f"未知工具: {name}"}, None
    try:
        result = t["func"](**(args or {}))
    except TypeError as e:
        return {"error": f"参数错误: {e}"}, None
    except Exception as e:
        return {"error": f"执行失败: {e}"}, None
    action = None
    if t["action"] and not (isinstance(result, dict) and result.get("error")):
        action = {}
        for k, v in t["action"].items():
            if isinstance(v, str) and v.startswith("{") and v.endswith("}"):
                action[k] = (args or {}).get(v[1:-1])
            else:
                action[k] = v
    return result, action


def tool_message_content(result, maxlen=2000):
    """工具结果 → tool message 字符串(截断防烧 context)"""
    try:
        s = _json.dumps(result, ensure_ascii=False)
    except Exception:
        s = str(result)
    if len(s) > maxlen:
        s = s[:maxlen] + f" …(截断, 原长 {len(s)} 字符)"
    return s


def list_brief(items, limit=8, fields=None):
    """列表摘要: 截断 + 可选字段白名单, 给模型看够用即可"""
    out = []
    for it in (items or [])[:limit]:
        if fields and isinstance(it, dict):
            out.append({k: it.get(k) for k in fields})
        else:
            out.append(it)
    if len(items or []) > limit:
        out.append({"…": f"共 {len(items)} 条, 仅示前 {limit} 条"})
    return out
