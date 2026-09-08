param(
    [Parameter(Mandatory = $false)]
    [string]$TargetFolder
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

Add-Type -AssemblyName System.Windows.Forms

$Version = '2.1.2'
$Repository = 'jaroslavkucacz-code/TURTO-Izolacni-nosniky'
$AppCommit = '138ea277739402297fedf8bb55ef2fe3fcba0f9b'
$UpdaterCommit = '0b49755f5a004e0eb5a7ae300502ec98d2e60af9'
$AppSha256 = '3c4d30c03b0f32a9959b1ae92a044aad5a183df07abd0e07dd20f22aac9843fe'
$UpdaterSha256 = 'a1579c8ef468a866eeb817aec8ca0309f2e0bb56b7944ec5615fca19d9599338'
$RuntimeMarker = '.turto_runtime_2_1_2.ok'
$StartupLog = 'startup_2_1_2.log'

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

    if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot 'app.pyw'))) {
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
    $markers = @('app.pyw', 'updater.py', 'Spustit_program.vbs', 'actions.sqlite3')
    foreach ($marker in $markers) {
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
            # URL ukazuje na neměnný Git commit a stažený obsah se ověřuje SHA-256.
            # Query string záměrně nepřidáváme kvůli kompatibilitě s Windows PowerShell 5.1.
            $downloadUrl = $Url
            Write-RecoveryLog $LogPath "Stahuji $Label, pokus $attempt/4"
            if ($attempt -eq 1) {
                Write-RecoveryLog $LogPath ("Zdroj {0}: {1}" -f $Label, $downloadUrl)
            }
            Invoke-WebRequest -UseBasicParsing -Uri $downloadUrl -OutFile $Destination -Headers @{
                'User-Agent' = 'TURTO-2.1.2-Recovery'
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

    $recoveryLog = Join-Path $target 'recovery_2_1_2.log'
    Set-Content -LiteralPath $recoveryLog -Encoding UTF8 -Value "TURTO $Version - nouzová oprava spuštění"
    Write-RecoveryLog $recoveryLog "Cílová složka: $target"

    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $backup = Join-Path $target ".recovery_before_2_1_2_$stamp"
    New-Item -ItemType Directory -Path $backup -Force | Out-Null

    foreach ($name in @('app.pyw', 'updater.py', $RuntimeMarker, $StartupLog)) {
        $source = Join-Path $target $name
        if (Test-Path -LiteralPath $source) {
            Copy-Item -LiteralPath $source -Destination (Join-Path $backup $name) -Force
        }
    }
    Write-RecoveryLog $recoveryLog "Záloha spouštěcí vrstvy: $backup"

    $tempDir = Join-Path $env:TEMP ("turto_recovery_" + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

    $appTemp = Join-Path $tempDir 'app.pyw'
    $updaterTemp = Join-Path $tempDir 'updater.py'

    $appUrl = "https://raw.githubusercontent.com/$Repository/$AppCommit/updates/2.1.2/app.pyw"
    $updaterUrl = "https://raw.githubusercontent.com/$Repository/$UpdaterCommit/updates/1.1.24/updater.py"

    Download-VerifiedFile $appUrl $appTemp $AppSha256 'app.pyw 2.1.2' $recoveryLog
    Download-VerifiedFile $updaterUrl $updaterTemp $UpdaterSha256 'updater.py' $recoveryLog

    Copy-Item -LiteralPath $appTemp -Destination (Join-Path $target 'app.pyw') -Force
    Copy-Item -LiteralPath $updaterTemp -Destination (Join-Path $target 'updater.py') -Force

    # Vynutí úplnou obnovu ověřeného runtime 2.1.0 při následujícím startu.
    Remove-Item -LiteralPath (Join-Path $target $RuntimeMarker) -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $target $StartupLog) -Force -ErrorAction SilentlyContinue

    Write-RecoveryLog $recoveryLog 'Spouštěcí vrstva 2.1.2 byla nainstalována. Databáze AKCÍ nebyla měněna.'

    Show-Info (
        "Opravná spouštěcí vrstva TURTO 2.1.2 byla nainstalována.`r`n`r`n" +
        "Databáze AKCÍ nebyla měněna.`r`n" +
        "Při prvním startu se znovu stáhne ověřený runtime 2.1.0 a modul smykových trnů.`r`n`r`n" +
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
