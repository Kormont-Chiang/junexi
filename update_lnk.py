import os
from win32com.client import Dispatch

desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
shell = Dispatch('WScript.Shell')

lnk = shell.CreateShortcut(os.path.join(desktop, '六月息.lnk'))
lnk.TargetPath = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
lnk.Arguments = r'--app=http://127.0.0.1:5000 --window-size=1400,900'
lnk.WorkingDirectory = r'C:\Users\Lenovo\.kimi_openclaw\workspace\historia-server'
lnk.IconLocation = r'C:\Windows\System32\shell32.dll,14'
lnk.Description = 'JuneXi History Panel'
lnk.Save()

print('OK')
