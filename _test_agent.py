# -*- coding: utf-8 -*-
"""R99 测试: AI agent 模式(工具注册表 + /api/ai/agent 循环 + 前端动作模板)

Flask test_client 免端口; 模型层 monkeypatch 掉 deepseek_chat(不真实联网);
CBDB 真实工具仅在本地库可用时执行(冷库 ~79s, 容忍慢)。
"""
import os
import sys
import json
import importlib.util

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = 0
FAIL = 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [pass] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {extra}")


# ── 0. 导入 CBDB 插件(注册 AI 工具) ──────────────────────
spec = importlib.util.spec_from_file_location(
    "jx_plugin_cbdb", os.path.join("plugins", "cbdb", "routes.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

import agent_tools

tools = agent_tools.get_openai_tools()
names = [t["function"]["name"] for t in tools]
print(f"已注册工具: {names}")
check("注册 4 件 CBDB 工具", len(tools) == 4, str(names))
check("schema 合规(name/desc/params)",
      all(t["function"]["name"] and t["function"]["description"]
          and t["function"]["parameters"].get("type") == "object" for t in tools))

# ── 1. execute_tool 边界 ─────────────────────────────────
r, a = agent_tools.execute_tool("no_such_tool", {})
check("未知工具 → error 且无动作", r.get("error") and a is None)
r, a = agent_tools.execute_tool("search_person", {})
check("缺必填参数 → error(不抛异常)", r.get("error") and a is None)

# ── 2. 真库工具(可用才跑) ────────────────────────────────
CBDB = mod.CBDBConnection
if CBDB.is_available():
    r, a = agent_tools.execute_tool("search_person", {"name": "王安石"})
    check("search_person 王安石 命中", r.get("total", 0) > 0, str(r)[:120])
    check("search_person 动作模板填充", a == {"type": "cbdb_search", "name": "王安石"}, str(a))
    hit = r["persons"][0]
    check("首条含 id/name", hit.get("id") and hit.get("name"), str(hit))

    wang = next((p for p in r["persons"] if p.get("name") == "王安石"), r["persons"][0])
    r2, a2 = agent_tools.execute_tool("get_person_detail", {"person_id": wang["id"]})
    check("get_person_detail 有内容且无 error", bool(r2) and not r2.get("error"), str(r2)[:120])
    check("detail 动作=cbdb_person", a2 == {"type": "cbdb_person", "id": wang["id"]}, str(a2))

    r3, a3 = agent_tools.execute_tool("show_persons_on_map", {"person_ids": [wang["id"]]})
    check("上图 单人返回 mapped_features", "mapped_features" in r3 and not r3.get("error"), str(r3)[:120])
    check("上图 动作带 ids", a3 and a3.get("type") == "cbdb_map" and a3.get("ids") == [wang["id"]], str(a3))

    # R99c: 模型把 id 序列化成字符串时不得逐字符拆解(“1762” → [1,7,6,2] 事故)
    r3s, a3s = agent_tools.execute_tool("show_persons_on_map", {"person_ids": str(wang["id"])})
    check("上图 字符串id 与列表id 结果一致", r3s.get("mapped_features") == r3.get("mapped_features"),
          f"str->{r3s.get('mapped_features')} list->{r3.get('mapped_features')}")
    r3c, _ = agent_tools.execute_tool("show_persons_on_map", {"person_ids": f"{wang['id']},1493"})
    r3l, _ = agent_tools.execute_tool("show_persons_on_map", {"person_ids": [wang["id"], 1493]})
    check("上图 逗号串 id 与列表一致", r3c.get("mapped_features") == r3l.get("mapped_features"),
          f"str->{r3c.get('mapped_features')} list->{r3l.get('mapped_features')}")

    r4, _ = agent_tools.execute_tool("list_person_kin", {"person_id": wang["id"], "kin": "mourning"})
    check("五服递归 total>0", r4.get("total", 0) > 0, str(r4)[:120])

    r5, a5 = agent_tools.execute_tool("get_person_detail", {"person_id": 99999999})
    check("不存在的人物 → error 且无动作", r5.get("error") and a5 is None)
else:
    print("  [skip] CBDB 本地库不可用, 真实工具测试跳过")

# ── 3. /api/ai/agent 循环(模型层打桩) ────────────────────
import app as appmod

client = appmod.app.test_client()


def make_fake_chat(script):
    """script: list, 第 i 次调用返回 script[i]"""
    state = {"n": 0, "tools_seen": []}

    def fake(messages, stream=False, model_id=None, tools=None):
        i = min(state["n"], len(script) - 1)
        state["n"] += 1
        state["tools_seen"].append(tools)
        return script[i]
    return fake, state


def msg_with_tool_call(name, args, cid="call_1"):
    return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
        {"id": cid, "type": "function",
         "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}]}}]}


def msg_final(text):
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


# 3.1 两轮: 先调 search_person, 再总结
fake, st = make_fake_chat([
    msg_with_tool_call("search_person", {"name": "王安石"}),
    msg_final("已检索王安石: 命中 10 条, 首条 ID 1762。已在 CBDB 页打开结果。"),
])
orig = appmod.deepseek_chat
appmod.deepseek_chat = fake
try:
    rv = client.post("/api/ai/agent", json={"message": "帮我查王安石"})
    data = rv.get_json()
finally:
    appmod.deepseek_chat = orig

check("agent 返回 response", "王安石" in (data.get("response") or ""), str(data)[:200])
check("agent 记录 1 步且成功", len(data.get("steps", [])) == 1 and data["steps"][0]["ok"])
check("agent 下发 cbdb_search 动作",
      data.get("actions") == [{"type": "cbdb_search", "name": "王安石"}], str(data.get("actions")))
check("工具传入了模型", st["tools_seen"] and st["tools_seen"][0])

# 3.2 模型报错透出
fake2, _ = make_fake_chat([{"error": "DeepSeek 额度不足"}])
appmod.deepseek_chat = fake2
try:
    rv = client.post("/api/ai/agent", json={"message": "查苏轼"})
    data2 = rv.get_json()
finally:
    appmod.deepseek_chat = orig
check("模型错误透出", "额度不足" in (data2.get("error") or ""), str(data2)[:150])

# 3.3 空消息 400 语义
rv = client.post("/api/ai/agent", json={"message": "  "})
check("空消息拒绝", rv.get_json().get("error"))

# 3.4 tool 结果回喂: 第二轮 messages 里应有 role=tool
captured = {}
def fake3(messages, stream=False, model_id=None, tools=None):
    captured["msgs"] = [dict(m) for m in messages]
    return msg_final("ok")
appmod.deepseek_chat = fake3
try:
    # 第一轮: 先给 tool_call, 让循环执行真实工具(search_person 可能慢/不可用 → 用桩工具)
    pass
finally:
    appmod.deepseek_chat = orig

# 用注册表临时注入一个假工具验证回喂结构
@agent_tools.tool("_echo_test", "测试回声", params={"type": "object", "properties": {"x": {"type": "string"}}})
def _echo(x=""):
    return {"echo": x}

calls = {"n": 0}
def fake4(messages, stream=False, model_id=None, tools=None):
    calls["n"] += 1
    if calls["n"] == 1:
        return msg_with_tool_call("_echo_test", {"x": "你好"})
    roles = [m["role"] for m in messages]
    assert roles.count("tool") == 1, f"tool 消息缺失: {roles}"
    tm = [m for m in messages if m["role"] == "tool"][0]
    assert tm.get("tool_call_id") == "call_1" and tm.get("name") == "_echo_test"
    assert "你好" in tm.get("content", "")
    return msg_final("收到回声")
appmod.deepseek_chat = fake4
try:
    rv = client.post("/api/ai/agent", json={"message": "回声测试"})
    data4 = rv.get_json()
finally:
    appmod.deepseek_chat = orig
check("tool 结果正确回喂(结构/字段)", data4.get("response") == "收到回声", str(data4)[:200])
check("假工具也生成动作? 无 action 模板 → 无动作", data4.get("actions") == [], str(data4.get("actions")))

print(f"\n=== {PASS} pass / {FAIL} fail ===")
sys.exit(1 if FAIL else 0)
