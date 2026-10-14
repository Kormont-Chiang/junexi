import re
lines = open('app.py', encoding='utf-8').read().split('\n')
for i, line in enumerate(lines, 1):
    if 'cbdb' in line.lower() and ('false' in line.lower() or 'status' in line.lower() or 'ready' in line.lower() or 'health' in line.lower()):
        print(f'{i}: {line.strip()[:100]}')
