param(
    [Parameter(Mandatory = $false)]
    [string]$TargetFolder
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

Add-Type -AssemblyName System.Windows.Forms

$Version = '2.2.24'
$Repository = 'jaroslavkucacz-code/TURTO-Izolacni-nosniky'
$AppCommit = '58d26464294f0f8277ee1d6b664bc565d76d0227'
$UpdaterCommit = '307c17bda050b38543f6a7f5cc228555b0698182'
$AppSha256 = 'e69ae3f91d28a10d9b558e3dcaa8eb75abaf7e33c4aa243f8e66506c2ba2f754'
$UpdaterSha256 = '2eb9a19329479615c41288d790a40aa8fe8a82280d49271c8fec42a132bf355e'
$RuntimeMarker = '.turto_runtime_current.ok'
$StartupLog = 'startup.log'
$RecoveryLogName = 'recovery.log'

function Show-Info([string]$Text) {
    [System.Windows.Forms.MessageBox]::Show(
        $Text,
        'TURTO - oprava spuštění',
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Information
    ) | Out-Null
}

function Show-Error([string]$Text) {
    [System.Windows.Forms.MessageBox]::Show(
        $Text,
        'TURTO - oprava spuštění',
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
}

function Select-TargetFolder {
    if ($TargetFolder) {
        return [System.IO.Path]::GetFullPath($TargetFolder)
    }

    if ($PSScriptRoot -and (
        (Test-Path (Join-Path $PSScriptRoot 'app.pyw')) -or
        (Test-Path (Join-Path $PSScriptRoot 'Spustit_program.vbs'))
    )) {
        return [System.IO.Path]::GetFullPath($PSScriptRoot)
    }

    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = 'Vyberte instalační složku TURTO.'
    $dialog.ShowNewFolderButton = $false
    if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
        throw 'Nebyla vybrána složka programu TURTO.'
    }
    return [System.IO.Path]::GetFullPath($dialog.SelectedPath)
}

function Test-TurtoFolder([string]$Folder) {
    return (
        (Test-Path (Join-Path $Folder 'app.pyw')) -or
        (Test-Path (Join-Path $Folder 'Spustit_program.vbs')) -or
        (Test-Path (Join-Path $Folder 'updater.py'))
    )
}

function Write-RecoveryLog([string]$Path, [string]$Text) {
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -LiteralPath $Path -Encoding UTF8 -Value "[$stamp] $Text"
}

function Download-VerifiedFile(
    [string]$Url,
    [string]$Destination,
    [string]$ExpectedSha256,
    [string]$Label,
    [string]$LogPath
) {
    $lastError = $null
    for ($attempt = 1; $attempt -le 4; $attempt++) {
        try {
            Write-RecoveryLog $LogPath "Stahuji $Label, pokus $attempt/4"
            Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $Destination -Headers @{
                'User-Agent' = 'TURTO-Recovery-2.2.24'
                'Cache-Control' = 'no-cache, no-store'
                'Pragma' = 'no-cache'
            }
            if (-not (Test-Path -LiteralPath $Destination)) {
                throw "Soubor $Label nebyl vytvořen."
            }
            if ((Get-Item -LiteralPath $Destination).Length -le 0) {
                throw "Stažený soubor $Label je prázdný."
            }
            $actual = (Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($actual -ne $ExpectedSha256.ToLowerInvariant()) {
                throw "Kontrolní součet $Label nesouhlasí. Očekáváno $ExpectedSha256, získáno $actual."
            }
            Write-RecoveryLog $LogPath "$Label ověřen SHA-256."
            return
        }
        catch {
            $lastError = $_.Exception.Message
            Remove-Item -LiteralPath $Destination -Force -ErrorAction SilentlyContinue
            if ($attempt -lt 4) {
                Start-Sleep -Seconds $attempt
            }
        }
    }
    throw "Nelze stáhnout nebo ověřit $Label.`r`n$lastError"
}

$target = $null
$recoveryLog = $null
$tempDir = $null

try {
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    }
    catch {
    }

    $target = Select-TargetFolder
    if (-not (Test-Path -LiteralPath $target -PathType Container)) {
        throw "Vybraná složka neexistuje:`r`n$target"
    }
    if (-not (Test-TurtoFolder $target)) {
        throw "Vybraná složka nevypadá jako instalace TURTO:`r`n$target"
    }

    $logDir = Join-Path $target 'Logy'
    $backupRoot = Join-Path (Join-Path $target 'Zaloha') 'Recovery'
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
    $recoveryLog = Join-Path $logDir $RecoveryLogName

    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $backup = Join-Path $backupRoot $stamp
    New-Item -ItemType Directory -Path $backup -Force | Out-Null

    foreach ($name in @('app.pyw', 'updater.py', $RuntimeMarker)) {
        $source = Join-Path $target $name
        if (Test-Path -LiteralPath $source) {
            Copy-Item -LiteralPath $source -Destination (Join-Path $backup $name) -Force
        }
    }
    foreach ($name in @($StartupLog, $RecoveryLogName)) {
        $source = Join-Path $logDir $name
        if (Test-Path -LiteralPath $source) {
            Copy-Item -LiteralPath $source -Destination (Join-Path $backup $name) -Force
        }
    }

    Set-Content -LiteralPath $recoveryLog -Encoding UTF8 -Value "TURTO $Version - nouzová oprava spuštění"
    Write-RecoveryLog $recoveryLog "Cílová složka: $target"
    Write-RecoveryLog $recoveryLog "Záloha spouštěcí vrstvy: $backup"

    $tempDir = Join-Path $env:TEMP ("turto_recovery_" + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    $appTemp = Join-Path $tempDir 'app.pyw'
    $updaterTemp = Join-Path $tempDir 'updater.py'

    $appUrl = "https://raw.githubusercontent.com/$Repository/$AppCommit/updates/2.2.24/app.pyw"
    $updaterUrl = "https://raw.githubusercontent.com/$Repository/$UpdaterCommit/updates/2.2.15/updater.py"

    Download-VerifiedFile $appUrl $appTemp $AppSha256 'app.pyw' $recoveryLog
    Download-VerifiedFile $updaterUrl $updaterTemp $UpdaterSha256 'updater.py' $recoveryLog

    Copy-Item -LiteralPath $appTemp -Destination (Join-Path $target 'app.pyw') -Force
    Copy-Item -LiteralPath $updaterTemp -Destination (Join-Path $target 'updater.py') -Force

    # Marker removal forces the verified bootstrap to validate/repair Program.
    Remove-Item -LiteralPath (Join-Path $target $RuntimeMarker) -Force -ErrorAction SilentlyContinue

    Write-RecoveryLog $recoveryLog 'Spouštěcí vrstva byla obnovena. actions.sqlite3 ani složka Program nebyly měněny.'

    Show-Info (
        "Spouštěcí vrstva TURTO $Version byla obnovena.`r`n`r`n" +
        "Databáze AKCÍ nebyla měněna.`r`n" +
        "Recovery záloha je uložena v Zaloha\Recovery a log v Logy\recovery.log.`r`n" +
        "Při prvním startu se složka Program ověří a případně bezpečně doplní.`r`n`r`n" +
        "Program se nyní pokusí spustit."
    )

    $vbs = Join-Path $target 'Spustit_program.vbs'
    $app = Join-Path $target 'app.pyw'
    if (Test-Path -LiteralPath $vbs) {
        Start-Process -FilePath 'wscript.exe' -ArgumentList ('"' + $vbs + '"') -WorkingDirectory $target
    }
    elseif (Get-Command 'pyw.exe' -ErrorAction SilentlyContinue) {
        Start-Process -FilePath 'pyw.exe' -ArgumentList ('"' + $app + '"') -WorkingDirectory $target
    }
    elseif (Get-Command 'py.exe' -ErrorAction SilentlyContinue) {
        Start-Process -FilePath 'py.exe' -ArgumentList @('-3', ('"' + $app + '"')) -WorkingDirectory $target
    }
    else {
        throw "Oprava byla dokončena, ale nebyl nalezen spouštěč Pythonu."
    }

    Write-RecoveryLog $recoveryLog 'Byl vyvolán start programu.'
    exit 0
}
catch {
    $message = $_.Exception.Message
    if ($recoveryLog) {
        try {
            Write-RecoveryLog $recoveryLog "CHYBA: $message"
        }
        catch {
        }
    }
    Show-Error (
        "Opravu TURTO se nepodařilo dokončit.`r`n`r`n$message" +
        $(if ($recoveryLog) { "`r`n`r`nPodrobnosti: $recoveryLog" } else { '' })
    )
    exit 1
}
finally {
    if ($tempDir -and (Test-Path -LiteralPath $tempDir)) {
        Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
