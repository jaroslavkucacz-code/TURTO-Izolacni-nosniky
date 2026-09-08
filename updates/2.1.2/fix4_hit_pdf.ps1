param(
    [Parameter(Mandatory = $false)]
    [string]$TargetFolder
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

Add-Type -AssemblyName System.Windows.Forms

$HotfixCommit = '754503c50f767f6d029a87bb95e3ede43fe5fd56'
$ExpectedSha256 = '62909e7ecbcc5f56d7dca077cf95421cb1ee10931599433557abece32d629ea8'
$RuntimeCommit = '2a0428af98b064770fffe84d430dee3388a1bfb9'
$HotfixUrl = 'https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/754503c50f767f6d029a87bb95e3ede43fe5fd56/updates/2.1.2/hit_pdf.py'

function Show-Info([string]$Text) {
    [System.Windows.Forms.MessageBox]::Show(
        $Text,
        'TURTO 2.1.2 - oprava PDF HIT',
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Information
    ) | Out-Null
}

function Show-Error([string]$Text) {
    [System.Windows.Forms.MessageBox]::Show(
        $Text,
        'TURTO 2.1.2 - oprava PDF HIT',
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
}

function Select-TargetFolder {
    if ($TargetFolder) {
        return [System.IO.Path]::GetFullPath($TargetFolder)
    }

    if ($PSScriptRoot -and (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'app.pyw'))) {
        return [System.IO.Path]::GetFullPath($PSScriptRoot)
    }

    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = 'Vyberte slozku programu TURTO, ve ktere je app.pyw.'
    $dialog.ShowNewFolderButton = $false
    if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
        throw 'Nebyla vybrana slozka programu TURTO.'
    }
    return [System.IO.Path]::GetFullPath($dialog.SelectedPath)
}

function Write-FixLog([string]$Path, [string]$Text) {
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -LiteralPath $Path -Encoding UTF8 -Value ('[{0}] {1}' -f $stamp, $Text)
}

$target = $null
$logPath = $null
$tempFile = $null

try {
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    }
    catch {
    }

    $target = Select-TargetFolder
    if (-not (Test-Path -LiteralPath $target -PathType Container)) {
        throw ('Vybrana slozka neexistuje: {0}' -f $target)
    }

    $app = Join-Path $target 'app.pyw'
    $targetFile = Join-Path $target 'hit_pdf.py'
    $previousFile = Join-Path $target 'hit_pdf_127.py'
    $runtimeMarker = Join-Path $target '.turto_runtime_2_1_2.ok'

    if (-not (Test-Path -LiteralPath $app -PathType Leaf)) {
        throw ('Ve vybrane slozce chybi app.pyw: {0}' -f $target)
    }
    if (-not (Test-Path -LiteralPath $targetFile -PathType Leaf)) {
        throw ('Ve vybrane slozce chybi hit_pdf.py: {0}' -f $target)
    }
    if (-not (Test-Path -LiteralPath $previousFile -PathType Leaf)) {
        throw ('Ve vybrane slozce chybi hit_pdf_127.py: {0}' -f $target)
    }
    if (-not (Test-Path -LiteralPath $runtimeMarker -PathType Leaf)) {
        throw 'Chybi marker runtime 2.1.2. Nejprve znovu spustte FIX3.'
    }

    $markerValue = (Get-Content -LiteralPath $runtimeMarker -Raw).Trim()
    if ($markerValue -ne $RuntimeCommit) {
        throw ('Runtime marker neodpovida ocekavane verzi. Nalezeno: {0}' -f $markerValue)
    }

    $logPath = Join-Path $target 'fix4_hit_pdf.log'
    Set-Content -LiteralPath $logPath -Encoding UTF8 -Value 'TURTO 2.1.2 - FIX4 kompatibility PDF HIT'
    Write-FixLog $logPath ('Cilova slozka: {0}' -f $target)
    Write-FixLog $logPath ('Hotfix commit: {0}' -f $HotfixCommit)

    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $backupDir = Join-Path $target ('.fix4_backup_{0}' -f $stamp)
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    Copy-Item -LiteralPath $targetFile -Destination (Join-Path $backupDir 'hit_pdf.py') -Force
    Write-FixLog $logPath ('Zaloha: {0}' -f $backupDir)

    $tempFile = Join-Path $target 'hit_pdf.py.fix4.tmp'
    Remove-Item -LiteralPath $tempFile -Force -ErrorAction SilentlyContinue

    Write-FixLog $logPath ('Stahuji hotfix z: {0}' -f $HotfixUrl)
    Invoke-WebRequest -UseBasicParsing -Uri $HotfixUrl -OutFile $tempFile -Headers @{
        'User-Agent' = 'TURTO-2.1.2-FIX4'
        'Cache-Control' = 'no-cache, no-store'
        'Pragma' = 'no-cache'
    }

    if (-not (Test-Path -LiteralPath $tempFile -PathType Leaf)) {
        throw 'Hotfix se nestahl.'
    }
    if ((Get-Item -LiteralPath $tempFile).Length -le 0) {
        throw 'Stazeny hotfix je prazdny.'
    }

    $actualSha256 = (Get-FileHash -LiteralPath $tempFile -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualSha256 -ne $ExpectedSha256) {
        throw ('Kontrolni soucet hotfixu nesouhlasi. Ocekavano {0}, ziskano {1}' -f $ExpectedSha256, $actualSha256)
    }
    Write-FixLog $logPath ('SHA-256 overeno: {0}' -f $actualSha256)

    Move-Item -LiteralPath $tempFile -Destination $targetFile -Force
    $tempFile = $null
    Write-FixLog $logPath 'hit_pdf.py byl nahrazen opravenou verzi.'

    $installedSha256 = (Get-FileHash -LiteralPath $targetFile -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($installedSha256 -ne $ExpectedSha256) {
        throw ('Kontrola po instalaci selhala. SHA-256: {0}' -f $installedSha256)
    }

    Write-FixLog $logPath 'FIX4 dokoncen. Databaze ani runtime marker nebyly meneny.'

    Show-Info (
        "Oprava PDF vrstvy HIT byla nainstalovana.`r`n`r`n" +
        "Databaze AKCI nebyla menena.`r`n" +
        "Program se nyni pokusi spustit."
    )

    $vbs = Join-Path $target 'Spustit_program.vbs'
    if (Test-Path -LiteralPath $vbs -PathType Leaf) {
        Start-Process -FilePath 'wscript.exe' -ArgumentList ('"' + $vbs + '"') -WorkingDirectory $target
    }
    elseif (Get-Command 'pyw.exe' -ErrorAction SilentlyContinue) {
        Start-Process -FilePath 'pyw.exe' -ArgumentList ('"' + $app + '"') -WorkingDirectory $target
    }
    elseif (Get-Command 'py.exe' -ErrorAction SilentlyContinue) {
        Start-Process -FilePath 'py.exe' -ArgumentList @('-3', ('"' + $app + '"')) -WorkingDirectory $target
    }
    else {
        throw 'Oprava byla nainstalovana, ale nebyl nalezen spoustec Pythonu.'
    }

    Write-FixLog $logPath 'Byl vyvolan start programu.'
    exit 0
}
catch {
    $message = $_.Exception.Message
    if ($logPath) {
        try {
            Write-FixLog $logPath ('CHYBA: {0}' -f $message)
        }
        catch {
        }
    }
    Show-Error (
        "FIX4 se nepodarilo dokoncit.`r`n`r`n" + $message +
        $(if ($logPath) { "`r`n`r`nPodrobnosti: $logPath" } else { '' })
    )
    exit 1
}
finally {
    if ($tempFile -and (Test-Path -LiteralPath $tempFile)) {
        Remove-Item -LiteralPath $tempFile -Force -ErrorAction SilentlyContinue
    }
}
