param(
    [Parameter(Mandatory = $false)]
    [string]$TargetFolder
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

Add-Type -AssemblyName System.Windows.Forms

$UpdaterUrl = 'https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/91a935d7aa025d8cf4a4856139af9e41df8d0b72/updates/2.1.3/updater.py'
$ExpectedGitBlobSha1 = 'a1e4b7941d34cd294ea7dd391ea5eabd0c620f34'

function Show-Info([string]$Text) {
    [System.Windows.Forms.MessageBox]::Show(
        $Text,
        'TURTO - oprava online aktualizace',
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Information
    ) | Out-Null
}

function Show-Error([string]$Text) {
    [System.Windows.Forms.MessageBox]::Show(
        $Text,
        'TURTO - oprava online aktualizace',
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

function Get-GitBlobSha1([string]$Path) {
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    $prefix = [System.Text.Encoding]::UTF8.GetBytes(('blob {0}' -f $bytes.Length) + [char]0)
    $combined = New-Object byte[] ($prefix.Length + $bytes.Length)
    [System.Array]::Copy($prefix, 0, $combined, 0, $prefix.Length)
    [System.Array]::Copy($bytes, 0, $combined, $prefix.Length, $bytes.Length)
    $sha1 = [System.Security.Cryptography.SHA1]::Create()
    try {
        $hash = $sha1.ComputeHash($combined)
    }
    finally {
        $sha1.Dispose()
    }
    return (($hash | ForEach-Object { $_.ToString('x2') }) -join '')
}

$target = $null
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
    $updater = Join-Path $target 'updater.py'
    if (-not (Test-Path -LiteralPath $app -PathType Leaf)) {
        throw ('Ve vybrane slozce chybi app.pyw: {0}' -f $target)
    }
    if (-not (Test-Path -LiteralPath $updater -PathType Leaf)) {
        throw ('Ve vybrane slozce chybi updater.py: {0}' -f $target)
    }

    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $backupDir = Join-Path $target ('.updater_backup_{0}' -f $stamp)
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    Copy-Item -LiteralPath $updater -Destination (Join-Path $backupDir 'updater.py') -Force

    $tempFile = Join-Path $target 'updater.py.new'
    Remove-Item -LiteralPath $tempFile -Force -ErrorAction SilentlyContinue

    Invoke-WebRequest -UseBasicParsing -Uri $UpdaterUrl -OutFile $tempFile -Headers @{
        'User-Agent' = 'TURTO-Updater-Repair-2.1.3'
        'Cache-Control' = 'no-cache, no-store'
        'Pragma' = 'no-cache'
    }

    if (-not (Test-Path -LiteralPath $tempFile -PathType Leaf)) {
        throw 'Novy updater se nestahl.'
    }

    $actualGitBlobSha1 = Get-GitBlobSha1 $tempFile
    if ($actualGitBlobSha1 -ne $ExpectedGitBlobSha1) {
        throw ('Git blob kontrola updateru nesouhlasi. Ocekavano {0}, ziskano {1}' -f $ExpectedGitBlobSha1, $actualGitBlobSha1)
    }

    Move-Item -LiteralPath $tempFile -Destination $updater -Force
    $tempFile = $null

    Show-Info (
        "Online aktualizator TURTO byl opraven.`r`n`r`n" +
        "Program se nyni znovu spusti. Potom kliknete na Aktualizace.`r`n`r`n" +
        "Databaze AKCI nebyla menena."
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
        throw 'Updater byl opraven, ale nebyl nalezen spoustec Pythonu.'
    }

    exit 0
}
catch {
    Show-Error ("Oprava online aktualizace se nezdarila.`r`n`r`n" + $_.Exception.Message)
    exit 1
}
finally {
    if ($tempFile -and (Test-Path -LiteralPath $tempFile)) {
        Remove-Item -LiteralPath $tempFile -Force -ErrorAction SilentlyContinue
    }
}
