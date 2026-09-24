Add-Type -AssemblyName System.Drawing

$root = "C:\Users\Lenovo\.kimi_openclaw\workspace\historia-server"
$log = New-Object System.Collections.Generic.List[string]
function Log($m){ $log.Add($m) | Out-Null }

$char  = [string][char]0x606F                 # xi (U+606F)
$paper = [System.Drawing.Color]::FromArgb(255, 245, 240, 225)  # xuan paper F5F0E1
$green = [System.Drawing.Color]::FromArgb(255,  63, 107,  79)  # pine green 3F6B4F

# ---- pick font: ancient-seal song if present, else clerical script ----
$pfc = New-Object System.Drawing.Text.PrivateFontCollection
$fontFile = $null
$guyin = [string][char]0x53E4 + [string][char]0x5370 + [string][char]0x5B8B  # gu-yin-song
foreach ($d in @("$env:LOCALAPPDATA\Microsoft\Windows\Fonts", "C:\Windows\Fonts")) {
  Get-ChildItem $d -File -ErrorAction SilentlyContinue | ForEach-Object {
    if (-not $script:fontFile -and $_.Name -like "*$guyin*" -and $_.Extension -match '^\.(ttf|ttc|otf)$') {
      $script:fontFile = $_.FullName
    }
  }
}
if (-not $fontFile) { $fontFile = "C:\Windows\Fonts\SIMLI.TTF" }
Log("fontFile=$fontFile")
$pfc.AddFontFile($fontFile)
$fam = $pfc.Families[0]
$style = [System.Drawing.FontStyle]::Regular
if (-not $fam.IsStyleAvailable($style)) { $style = [System.Drawing.FontStyle]::Bold }
Log("family=$($fam.Name) style=$style")

# ---- master 1024x1024 ----
$S = 1024
$bmp = New-Object System.Drawing.Bitmap($S, $S)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.Clear($paper)

# seal layer (green block + knocked-out char), rotated later like a hand stamp
$seal = New-Object System.Drawing.Bitmap($S, $S)
$gs = [System.Drawing.Graphics]::FromImage($seal)
$gs.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$gs.Clear([System.Drawing.Color]::Transparent)
$gs.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAlias

$side = 660
$x0 = ($S - $side) / 2
$y0 = ($S - $side) / 2
$rr = 18
$path = New-Object System.Drawing.Drawing2D.GraphicsPath
$path.AddArc($x0, $y0, $rr*2, $rr*2, 180, 90)
$path.AddArc($x0+$side-$rr*2, $y0, $rr*2, $rr*2, 270, 90)
$path.AddArc($x0+$side-$rr*2, $y0+$side-$rr*2, $rr*2, $rr*2, 0, 90)
$path.AddArc($x0, $y0+$side-$rr*2, $rr*2, $rr*2, 90, 90)
$path.CloseFigure()
$gs.FillPath((New-Object System.Drawing.SolidBrush($green)), $path)

$sf = [System.Drawing.StringFormat]::GenericTypographic.Clone()
$sf.Alignment = [System.Drawing.StringAlignment]::Near
$sf.LineAlignment = [System.Drawing.StringAlignment]::Near
$sf.FormatFlags = $sf.FormatFlags -bor [System.Drawing.StringFormatFlags]::NoClip

$targetW = $side * 0.76
$em = 200
$f1 = New-Object System.Drawing.Font($fam, $em, $style, [System.Drawing.GraphicsUnit]::Pixel)
$m1 = $gs.MeasureString($char, $f1, [System.Drawing.PointF]::Empty, $sf)
$em2 = [int]($em * ($targetW / $m1.Width))
$f1.Dispose()
$f2 = New-Object System.Drawing.Font($fam, $em2, $style, [System.Drawing.GraphicsUnit]::Pixel)
$m2 = $gs.MeasureString($char, $f2, [System.Drawing.PointF]::Empty, $sf)
$px = ($S - $m2.Width) / 2 - $m2.X
$py = ($S - $m2.Height) / 2 - $m2.Y
Log("em=$em2 w=$([int]$m2.Width) h=$([int]$m2.Height)")
$gs.DrawString($char, $f2, (New-Object System.Drawing.SolidBrush($paper)), (New-Object System.Drawing.PointF($px, $py)), $sf)
$f2.Dispose()
$gs.Dispose()

# stamp it on the paper with a slight tilt
$g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$g.TranslateTransform($S/2, $S/2)
$g.RotateTransform(-2)
$g.TranslateTransform(-$S/2, -$S/2)
$g.DrawImage($seal, 0, 0)
$g.Dispose()

$bmp.Save("$root\icon-preview.png", [System.Drawing.Imaging.ImageFormat]::Png)

# ---- multi-size ICO (PNG payloads, Vista+ safe) ----
$sizes = @(16, 20, 24, 32, 40, 48, 64, 128, 256)
$pngs = @{}
foreach ($s in $sizes) {
  $t = New-Object System.Drawing.Bitmap($s, $s)
  $gt = [System.Drawing.Graphics]::FromImage($t)
  $gt.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $gt.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
  $gt.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
  $gt.DrawImage($bmp, (New-Object System.Drawing.Rectangle(0, 0, $s, $s)))
  $gt.Dispose()
  $ms = New-Object System.IO.MemoryStream
  $t.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
  $pngs[[int]$s] = $ms.ToArray()
  $t.Dispose()
}
$icoPath = "$root\app.ico"
$fs = [System.IO.File]::Create($icoPath)
$bw = New-Object System.IO.BinaryWriter($fs)
$bw.Write([UInt16]0)
$bw.Write([UInt16]1)
$bw.Write([UInt16]$sizes.Count)
$offset = 6 + 16 * $sizes.Count
foreach ($s in $sizes) {
  $b = $pngs[[int]$s]
  $bw.Write([Byte]($s % 256))
  $bw.Write([Byte]($s % 256))
  $bw.Write([Byte]0)
  $bw.Write([Byte]0)
  $bw.Write([UInt16]1)
  $bw.Write([UInt16]32)
  $bw.Write([UInt32]$b.Length)
  $bw.Write([UInt32]$offset)
  $offset += $b.Length
}
foreach ($s in $sizes) { $bw.Write($pngs[[int]$s]) }
$bw.Close()
$fs.Close()
Copy-Item $icoPath "$root\static\favicon.ico" -Force
Log("ico=" + (Get-Item $icoPath).Length + " bytes; preview+ico synced")

[System.IO.File]::WriteAllLines("$root\_seal_log.txt", $log, (New-Object System.Text.UTF8Encoding($false)))
Write-Output "seal-done"
