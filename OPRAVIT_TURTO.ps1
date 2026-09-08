param(
    [Parameter(Mandatory = $false)]
    [string]$TargetFolder
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

Add-Type -AssemblyName System.Windows.Forms

$Version = '2.2.1'
$Repository = 'jaroslavkucacz-code/TURTO-Izolacni-nosniky'
$AppCommit = '40d455246a699eadd8b2179038073f6676cbacd6'
$UpdaterCommit = '5f395e56a8911e12783bdbd8378592963352cf69'
$AppSha256 = 'eb60e0f863e6a9d8236f7c8a81417d9d8ff632df20fbf5bf85e2e1e77e580af7'
$UpdaterSha256 = '9a421f4560dc7baa886b5781e3ad255eb71ab14941bb64990fa543b64c3fc706'
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
    $dialog.Description = 'Vyberte složku, ve které je nainstalovaný program TURTO (obsahuje app.pyw / Spustit_program.vbs).'
    $dialog.ShowNewFolderButton = $false
    if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
        throw 'Nebyla vybrána složka programu TURTO.'
    }
    return [System.IO.Path]::GetFullPath($dialog.SelectedPath)
}

function Test-TurtoFolder([string]$Folder) {
    foreach ($marker in @('app.pyw', 'updater.py', 'Spustit_program.vbs')) {
        if (Test-Path (Join-Path $Folder $marker)) {
            return $true
        }
    }
    return $false
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
            if ($attempt -eq 1) {
                Write-RecoveryLog $LogPath ("Zdroj {0}: {1}" -f $Label, $Url)
            }
            Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $Destination -Headers @{
                'User-Agent' = 'TURTO-Recovery-2.2.1'
                'Cache-Control' = 'no-cache, no-store'
                'Pragma' = 'no-cache'
            }

            if (-not (Test-Path $Destination)) {
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
        # Na novějších PowerShell/.NET není nastavení potřeba.
    }

    $target = Select-TargetFolder
    if (-not (Test-Path -LiteralPath $target -PathType Container)) {
        throw "Vybraná složka neexistuje:`r`n$target"
    }
    if (-not (Test-TurtoFolder $target)) {
        throw "Vybraná složka nevypadá jako instalace TURTO.`r`n`r`n$target`r`n`r`nVyberte složku obsahující app.pyw nebo Spustit_program.vbs."
    }

    $recoveryLog = Join-Path $target $RecoveryLogName

    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $backup = Join-Path $target ".recovery_backup_$stamp"
    New-Item -ItemType Directory -Path $backup -Force | Out-Null

    $backupNames = @(
        'app.pyw',
        'updater.py',
        $RuntimeMarker,
        $StartupLog,
        $RecoveryLogName,
        '.turto_runtime_2_1_2.ok',
        'startup_2_1_2.log',
        'recovery_2_1_2.log'
    )
    foreach ($name in $backupNames) {
        $source = Join-Path $target $name
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

    $appUrl = "https://raw.githubusercontent.com/$Repository/$AppCommit/updates/2.2.1/app.pyw"
    $updaterUrl = "https://raw.githubusercontent.com/$Repository/$UpdaterCommit/updates/2.2.1/updater.py"

    Download-VerifiedFile $appUrl $appTemp $AppSha256 'app.pyw' $recoveryLog
    Download-VerifiedFile $updaterUrl $updaterTemp $UpdaterSha256 'updater.py' $recoveryLog

    Copy-Item -LiteralPath $appTemp -Destination (Join-Path $target 'app.pyw') -Force
    Copy-Item -LiteralPath $updaterTemp -Destination (Join-Path $target 'updater.py') -Force

    # Vynutí obnovu současné ověřené runtime sady při následujícím startu.
    Remove-Item -LiteralPath (Join-Path $target $RuntimeMarker) -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $target '.turto_runtime_2_1_2.ok') -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $target $StartupLog) -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $target 'startup_2_1_2.log') -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $target 'recovery_2_1_2.log') -Force -ErrorAction SilentlyContinue

    Write-RecoveryLog $recoveryLog 'Aktuální spouštěcí vrstva byla nainstalována. Databáze AKCÍ nebyla měněna.'

    Show-Info (
        "Aktuální spouštěcí vrstva TURTO byla obnovena.`r`n`r`n" +
        "Databáze AKCÍ nebyla měněna.`r`n" +
        "Při prvním startu se ověří a případně obnoví současná runtime sada.`r`n`r`n" +
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
        throw "Oprava byla dokončena, ale nebyl nalezen spouštěč Pythonu. Spusťte ručně app.pyw v této složce:`r`n$target"
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
