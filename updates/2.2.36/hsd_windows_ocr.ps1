# Local Windows OCR. Receives only a file path; no file text is executed.
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime] > $null
[Windows.Storage.FileAccessMode, Windows.Storage, ContentType = WindowsRuntime] > $null
[Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime] > $null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime] > $null
[Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType = WindowsRuntime] > $null
[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] > $null
[Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType = WindowsRuntime] > $null
[Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime] > $null
function Await($operation, [Type]$type) {
    $method = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetGenericArguments().Count -eq 1 -and
        $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    } | Select-Object -First 1
    $task = $method.MakeGenericMethod($type).Invoke($null, @($operation))
    $task.Wait()
    return $task.Result
}
$stream = $null
$bitmap = $null
try {
    $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($env:TURTO_OCR_INPUT)) ([Windows.Storage.StorageFile])
    $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    if ($null -eq $engine) {
        $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new('en-US'))
    }
    if ($null -eq $engine) { throw 'Windows OCR language is unavailable. Install an OCR language in Windows language settings.' }
    $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    $words = @()
    foreach ($line in $result.Lines) {
        foreach ($word in $line.Words) {
            $r = $word.BoundingRect
            $words += @{text=$word.Text; x=$r.X; y=$r.Y; w=$r.Width; h=$r.Height}
        }
    }
    ConvertTo-Json -InputObject @($words) -Compress -Depth 5
} finally {
    if ($null -ne $bitmap) { $bitmap.Dispose() }
    if ($null -ne $stream) { $stream.Dispose() }
}
