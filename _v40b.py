"""R40b 回归：主题系统四步验证"""
from app import app
c = app.test_client()

# 1. index.html 注入
r = c.get('/')
h = r.data.decode('utf-8')
assert r.status_code == 200
assert 'jxSetTheme' in h, 'theme script missing'
assert 'themeToggleBtn' in h, 'theme button missing'
assert 'jx-theme' in h, 'localStorage key missing'
print('1. index.html theme injection OK')

# 2. CSS 主题块
r2 = c.get('/static/css/style.css')
css = r2.data.decode('utf-8')
assert r2.status_code == 200
for t in ['light', 'sepia', 'morandi']:
    assert f'[data-theme="{t}"]' in css, f'{t} theme block missing'
# short-name aliases
for alias in ['--bg: var(--bg-primary)', '--fg: var(--text-primary)',
              '--text: var(--text-primary)', '--muted: var(--text-muted)',
              '--panel: var(--bg-card)', '--border: var(--border-color)']:
    assert alias in css, f'alias missing: {alias}'
print('2. CSS theme blocks + aliases OK')

# 3. Brace balance
assert css.count('{') == css.count('}'), 'unbalanced braces'
print('3. CSS brace balance OK')

# 4. Root block count (should be 2: main vars + alias)
import re
root_count = len(re.findall(r':root\s*\{', css))
assert root_count == 2, f'Expected 2 :root blocks, got {root_count}'
print('4. Root blocks = 2 (main + alias) OK')

print('\nR40b ALL CHECKS PASSED')
