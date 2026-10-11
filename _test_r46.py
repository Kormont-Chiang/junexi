"""R46 框架加固测试：全局错误处理 + API 请求日志 + 404/405 JSON"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import app

client = app.test_client()
passed = 0
failed = 0

def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name} {detail}")

print("R46 框架加固测试")

# 1. API 404 returns JSON
r = client.get("/api/nonexistent")
check("API 404 returns JSON", r.status_code == 404 and r.is_json)
if r.is_json:
    check("API 404 has ok=False", r.get_json().get("ok") == False)

# 2. API 405 returns JSON
r = client.post("/api/status")  # GET-only route
check("API 405 returns JSON", r.status_code == 405 and r.is_json)

# 3. Non-API 404 returns HTML (Flask default)
r = client.get("/nonexistent-page")
check("Non-API 404 returns HTML", r.status_code == 404 and not r.is_json)

# 4. Normal API still works
r = client.get("/api/status")
check("API /api/status still works", r.status_code == 200 and r.is_json)

# 5. Normal route still works
r = client.get("/")
check("Route / still works", r.status_code == 200)

# 6. Plugins API works
r = client.get("/api/plugins")
check("API /api/plugins still works", r.status_code == 200 and r.is_json)

# 7. Response has no-store header
r = client.get("/api/status")
check("No-store header present", r.headers.get("Cache-Control") == "no-store")

print(f"\nR46: {passed} pass, {failed} fail")
sys.exit(1 if failed > 0 else 0)
