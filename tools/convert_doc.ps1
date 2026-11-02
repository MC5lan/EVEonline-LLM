# Convert legacy .doc files to plain text using Word COM.
#
# Why Word: .doc is an OLE compound document. The body lives in the
# WordDocument stream and may be split into fast-save segments. No pure
# library parses it reliably, but Word itself is the authoritative parser
# and it is already installed on this machine.
#
# NOTE 1: keep this file ASCII-only. Windows PowerShell 5.1 reads .ps1 as
#         ANSI and would corrupt any non-ASCII bytes, breaking the parser.
# NOTE 2: do NOT name a parameter -Input: $Input is an automatic variable
#         and the binding silently yields an empty value.
#
# Usage:
#   powershell -NoProfile -File tools/convert_doc.ps1 -InDir D:\Game\eve_raw -OutDir data\converted

param(
    [Parameter(Mandatory = $true)][string]$InDir,
    [Parameter(Mandatory = $true)][string]$OutDir
)

$ErrorActionPreference = 'Continue'
$src = (Resolve-Path -LiteralPath $InDir).Path
$dst = $OutDir
if (-not [System.IO.Path]::IsPathRooted($dst)) {
    $dst = Join-Path (Get-Location).Path $dst
}
New-Item -ItemType Directory -Force -Path $dst | Out-Null

# NOTE 3: -Filter *.doc also matches *.docx on Windows (8.3 short names),
#         which would re-convert every docx through Word and create "_1"
#         duplicates. Filter on the exact extension instead.
$files = Get-ChildItem -LiteralPath $src -Recurse -File |
    Where-Object { $_.Extension -eq '.doc' }
if (-not $files) { Write-Output "no .doc files"; exit 0 }
Write-Output ("found {0} .doc files, starting Word..." -f $files.Count)

$utf8 = New-Object System.Text.UTF8Encoding($false)
$md5 = [System.Security.Cryptography.MD5]::Create()
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0

$seen = @{}
$manifest = @()
$okCount = 0
$totalChars = 0

try {
    foreach ($f in $files) {
        $name = [System.IO.Path]::GetFileNameWithoutExtension($f.Name)
        $clean = ($name -replace '[\\/:*?"<>|]', '_')
        if ($clean.Length -gt 120) { $clean = $clean.Substring(0, 120) }

        $doc = $null
        try {
            $doc = $word.Documents.Open($f.FullName, $false, $true, $false)
            $text = $doc.Content.Text
            $doc.Close($false)
            $doc = $null

            $text = $text -replace "`r`n", "`n" -replace "`r", "`n"
            $text = $text.Trim()

            if ($text.Length -lt 50) {
                Write-Output ("  [x] {0}  too short ({1})" -f $f.Name, $text.Length)
                $manifest += [pscustomobject]@{ src = $f.Name; status = "short"; chars = $text.Length }
                continue
            }

            $hash = [System.BitConverter]::ToString(
                $md5.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($text)))
            if ($seen.ContainsKey($hash)) {
                Write-Output ("  [=] {0}  duplicate" -f $f.Name)
                $manifest += [pscustomobject]@{ src = $f.Name; status = "dup"; chars = $text.Length }
                continue
            }
            $seen[$hash] = $true

            $outFile = Join-Path $dst ($clean + ".md")
            $i = 1
            while (Test-Path -LiteralPath $outFile) {
                $outFile = Join-Path $dst ("{0}_{1}.md" -f $clean, $i)
                $i++
            }

            $head = "<!-- source: " + $f.FullName + " -->`n<!-- converter: word-com chars: " + $text.Length + " -->`n`n"
            [System.IO.File]::WriteAllText($outFile, $head + $text, $utf8)

            $okCount++
            $totalChars += $text.Length
            Write-Output ("  [+] {0}  {1} chars" -f $f.Name, $text.Length)
            $manifest += [pscustomobject]@{ src = $f.Name; out = (Split-Path $outFile -Leaf); status = "ok"; chars = $text.Length }
        }
        catch {
            Write-Output ("  [x] {0}  FAILED: {1}" -f $f.Name, $_.Exception.Message)
            $manifest += [pscustomobject]@{ src = $f.Name; status = "error"; chars = 0 }
            if ($doc) { try { $doc.Close($false) } catch {} }
        }
    }
}
finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
    [GC]::Collect()
}

$manifest | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $dst "_manifest_doc.json") -Encoding UTF8
Write-Output ("[doc] converted {0} / {1}, {2} chars -> {3}" -f $okCount, $files.Count, $totalChars, $dst)
