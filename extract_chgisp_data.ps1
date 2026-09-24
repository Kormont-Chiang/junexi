# 六月息 CHGIS 数据自动化解压脚本
# 需要安装 7-Zip (https://www.7-zip.org/) 或 WinRAR
# 运行方式: 右键点击此文件 → 使用 PowerShell 运行

$downloadDir = "C:\Users\Lenovo\Downloads"
$targetDir = "C:\Users\Lenovo\.kimi_openclaw\workspace\historia-server\chgis_data"

# 查找 7-Zip
$7zip = $null
$7zipPaths = @(
    "C:\Program Files\7-Zip\7z.exe",
    "C:\Program Files (x86)\7-Zip\7z.exe",
    (Join-Path $env:ProgramFiles "7-Zip\7z.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "7-Zip\7z.exe")
)
foreach ($path in $7zipPaths) {
    if (Test-Path $path) {
        $7zip = $path
        break
    }
}

# 查找 WinRAR
$winrar = $null
$winrarPaths = @(
    "C:\Program Files\WinRAR\UnRAR.exe",
    "C:\Program Files (x86)\WinRAR\UnRAR.exe"
)
foreach ($path in $winrarPaths) {
    if (Test-Path $path) {
        $winrar = $path
        break
    }
}

if (-not $7zip -and -not $winrar) {
    Write-Host "==========================================" -ForegroundColor Red
    Write-Host "  未找到解压工具！" -ForegroundColor Red
    Write-Host "==========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "请安装 7-Zip（推荐，免费）:"
    Write-Host "  https://www.7-zip.org/"
    Write-Host ""
    Write-Host "安装后重新运行此脚本。"
    Write-Host ""
    Read-Host "按 Enter 退出"
    exit 1
}

# 创建目标目录
New-Item -ItemType Directory -Path $targetDir -Force | Out-Null

# RAR 文件列表
$rarFiles = @(
    "D561EDF6847374AA20E92AF4991_D955CC9E_2E432.rar",
    "8DCFD1E648133808134CFD5410E_14C9F9A0_264BE.rar",
    "1B7B3931E5384423C7D714847E9_9271D219_A2ED.rar",
    "225BC03A0CAD180DCF42EFD4FAC_50FC4619_26B4D0.rar",
    "061AEDD5ECAFE8D3516A69EF6A5_AD87382D_2FDB.rar",
    "91DFB945E49E287954B6336364B_BFBDD629_1F02C8.rar",
    "F3CC906138A5511419E98B3F6E7_8FEE9441_5D3.rar",
    "685B0CA2F6EC1F0C9A428260A72_3A2AF387_FD66.rar"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  六月息 CHGIS 数据解压" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

foreach ($rarName in $rarFiles) {
    $rarPath = Join-Path $downloadDir $rarName
    if (-not (Test-Path $rarPath)) {
        Write-Host "  跳过: $rarName (文件不存在)" -ForegroundColor Yellow
        continue
    }
    
    Write-Host "  解压: $rarName ..." -NoNewline
    
    try {
        if ($7zip) {
            & $7zip x "$rarPath" -o"$targetDir" -y | Out-Null
        } else {
            & $winrar x -y "$rarPath" "$targetDir\" | Out-Null
        }
        Write-Host "  完成" -ForegroundColor Green
    } catch {
        Write-Host "  失败: $_" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  解压完成！" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "数据已保存到: $targetDir"
Write-Host ""
Write-Host "文件列表:"
Get-ChildItem -Path $targetDir -File | ForEach-Object {
    Write-Host "  $($_.Name.PadRight(50)) $([math]::Round($_.Length/1024, 1)) KB"
}
Write-Host ""
Read-Host "按 Enter 退出"
