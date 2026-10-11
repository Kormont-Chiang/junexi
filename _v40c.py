"""R40c 验证：插件皮肤包接口"""
from app import app
c = app.test_client()

# 1. /api/plugins 返回 themes 字段
r = c.get('/api/plugins')
d = r.get_json()
assert r.status_code == 200
assert 'themes' in d, 'themes key missing from /api/plugins'
print('1. /api/plugins has themes key OK')

# 2. themes is a dict (may be empty if no plugin declares theme.css)
themes = d.get('themes', {})
assert isinstance(themes, dict), 'themes should be dict'
print(f'2. themes dict: {themes}')

# 3. index.html 包含 _injectPluginThemes
r2 = c.get('/')
html = r2.data.decode('utf-8')
assert '_injectPluginThemes' in html, 'plugin theme injector missing'
assert '_removePluginThemes' in html, 'plugin theme remover missing'
print('3. index.html theme injector OK')

# 4. CSS version bumped
assert 'style.css?v=45' in html, 'CSS version not bumped'
print('4. CSS v=45 OK')

print('\nR40c ALL CHECKS PASSED')
