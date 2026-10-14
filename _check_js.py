import subprocess, sys
code = open('static/js/app.js', encoding='utf-8').read()
try:
    compile(code, 'app.js', 'exec')
    print('JS syntax OK')
except SyntaxError as e:
    print(f'Error: {e}')
