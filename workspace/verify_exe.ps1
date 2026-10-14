# E2E verify (ASCII only): launch exe, login admin/admin, open a library, screenshot steps.
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class U32 {
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(int f, int dx, int dy, int d, int e);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  public struct RECT { public int Left, Top, Right, Bottom; }
}
"@

$exe = (Get-ChildItem "$PWD\*.exe" | Select-Object -First 1).FullName
if (-not $exe) { throw "no exe found in $PWD" }
$OUT = "$PWD\.screenshots"
New-Item -ItemType Directory -Force -Path $OUT | Out-Null

function Shot($name) {
  $vs = [System.Windows.Forms.SystemInformation]::VirtualScreen
  $bmp = New-Object System.Drawing.Bitmap $vs.Width, $vs.Height
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($vs.Left, $vs.Top, 0, 0, $bmp.Size)
  $bmp.Save("$OUT\$name.png")
  $g.Dispose(); $bmp.Dispose()
  Write-Host "saved $name"
}

function Wait-Title($proc, $pattern, $sec) {
  for ($i = 0; $i -lt $sec; $i++) {
    Start-Sleep -Seconds 1
    $proc.Refresh()
    if ($proc.HasExited) { throw "exe exited early, code=$($proc.ExitCode)" }
    if ($proc.MainWindowTitle -match $pattern) { return $proc.MainWindowTitle }
  }
  $cur = $proc.MainWindowTitle
  throw "timeout waiting /$pattern/, current=[$cur]"
}

function Click-At($x, $y) {
  [U32]::SetCursorPos($x, $y) | Out-Null
  Start-Sleep -Milliseconds 200
  [U32]::mouse_event(0x0002, 0, 0, 0, 0)
  Start-Sleep -Milliseconds 80
  [U32]::mouse_event(0x0004, 0, 0, 0, 0)
}

function Find-WindowProc {
  Get-Process | Where-Object { $_.Path -eq $exe -and $_.MainWindowTitle -ne "" } |
    Select-Object -First 1
}

$p = Start-Process -FilePath $exe -PassThru
Write-Host "launched pid=$($p.Id) exe=$exe"

try {
  # onefile bootloader spawns a child process that owns the window: poll for it
  $w = $null
  for ($i = 0; $i -lt 60 -and -not $w; $i++) {
    Start-Sleep -Seconds 1
    $w = Find-WindowProc
  }
  if (-not $w) { throw "no window appeared within 60s" }
  $t = $w.MainWindowTitle
  Write-Host "OK first window: $t (pid=$($w.Id))"
  Start-Sleep -Seconds 1
  Shot "exe_1_login"

  $ws = New-Object -ComObject WScript.Shell
  $ws.AppActivate($w.Id) | Out-Null
  Start-Sleep -Milliseconds 500
  $ws.SendKeys("{TAB}")
  Start-Sleep -Milliseconds 200
  $ws.SendKeys("admin")
  Start-Sleep -Milliseconds 200
  Shot "exe_2_filled"
  $ws.SendKeys("{ENTER}")
  Write-Host "credentials submitted"

  Start-Sleep -Seconds 3
  $w = Find-WindowProc
  $t2 = if ($w) { $w.MainWindowTitle } else { "" }
  Write-Host "after login window: $t2"
  Shot "exe_3_after_login"

  if ($t2 -eq $t) { throw "login rejected: still on the same dialog [$t2]" }

  # on picker: select the first library row, then click the bottom-right open button
  $r = New-Object U32+RECT
  [U32]::GetWindowRect($w.MainWindowHandle, [ref]$r) | Out-Null
  $ww = $r.Right - $r.Left
  $wh = $r.Bottom - $r.Top
  Click-At ($r.Left + [int]($ww * 0.45)) ($r.Top + [int]($wh * 0.45))
  Write-Host "clicked first library row"
  Start-Sleep -Seconds 1
  Click-At ($r.Right - 80) ($r.Bottom - 32)
  Write-Host "clicked open button"
  Start-Sleep -Seconds 3
  $w = Find-WindowProc
  $t3 = if ($w) { $w.MainWindowTitle } else { "" }
  Shot "exe_4_main"

  if ($t3 -ne $t2 -and $t3 -ne "") {
    Write-Host "VERIFY-PASS main window reached: $t3"
  } else {
    throw "did not reach main window, current=[$t3]"
  }
}
finally {
  Get-Process | Where-Object { $_.Path -eq $exe } | Stop-Process -Force -ErrorAction SilentlyContinue
  Write-Host "exe closed"
}
