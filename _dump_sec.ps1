# 拉取最近4小时的失败登录/锁定事件，输出到 _sec.txt
$out = "C:\Users\Lenovo\.kimi_openclaw\workspace\historia-server\_sec.txt"
$since = (Get-Date).AddHours(-4)
$lines = @()
try {
    $evs = Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4625,4740; StartTime=$since} -ErrorAction Stop
    foreach ($e in $evs) {
        $x = [xml]$e.ToXml()
        $d = @{}
        foreach ($n in $x.Event.EventData.Data) { $d[$n.Name] = $n.'#text' }
        $lines += ($e.TimeCreated.ToString('MM-dd HH:mm:ss') + ' id=' + $e.Id + ' 类型=' + $d.LogonType + ' 用户=' + $d.TargetUserName + ' 进程=' + $d.ProcessName + ' 源IP=' + $d.IpAddress + ' 子码=' + $d.SubStatus)
    }
} catch {
    $lines += ("ERROR: " + $_.Exception.Message)
}
$lines | Out-File -Width 260 -Encoding utf8 $out
Write-Host ("done, lines=" + $lines.Count + " -> " + $out)
