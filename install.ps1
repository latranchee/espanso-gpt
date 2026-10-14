# Sets up espanso-gpt on this machine. Safe to re-run: after a git pull, or after
# fixing something it reports.
#   .\install.ps1                  everything
#   .\install.ps1 -SkipDictation   no F8 daemon: no Startup shortcut, no xAI check
param(
    [switch]$SkipDictation
)

Add-Type -AssemblyName System.Net.Http

$MinPythonVersion = [version]'3.10'
$DefaultProxyUrl = 'http://127.0.0.1:8765'
$DefaultModel = 'gpt-6-luna'
$EspansoCmd = Join-Path $env:LOCALAPPDATA 'Programs\Espanso\espanso.cmd'
$ShortcutPath = Join-Path ([Environment]::GetFolderPath('Startup')) 'espanso_push_to_talk.lnk'
$ShortcutDescription = 'Tap F8 to dictate into a bubble by the mouse, click an input to paste (xAI streaming STT + gpt-6-luna)'
$OpenAiProvider = [pscustomobject]@{
    Name = 'openai_espanso'; Secret = 'oai_espanso'; BaseUrl = 'https://api.openai.com'
    ProbePath = "/v1/models/$DefaultModel"; MaxBodyBytes = 26214400
}
$XaiProvider = [pscustomobject]@{
    Name = 'xai'; Secret = 'xai'; BaseUrl = 'https://api.x.ai'
    ProbePath = '/v1/models'; MaxBodyBytes = 10485760
}

function New-CheckResult([bool]$Ok, [string]$Message) {
    [pscustomobject]@{ Ok = $Ok; Message = $Message }
}

function Write-Heading([string]$Title) {
    Write-Host ''
    Write-Host $Title -ForegroundColor Cyan
}

function Show-Result($Result) {
    $label, $color = if ($Result.Ok) { 'ok ', 'Green' } else { 'fix', 'Yellow' }
    $lines = $Result.Message -split "`n"
    Write-Host "  [$label] $($lines[0])" -ForegroundColor $color
    $lines | Select-Object -Skip 1 | ForEach-Object { Write-Host "        $_" -ForegroundColor $color }
    $Result
}

function Test-ConfigLocation([string]$RepoRoot) {
    $expected = Join-Path $env:APPDATA 'espanso'
    if ($RepoRoot.TrimEnd('\') -eq $expected) {
        return New-CheckResult $true "Repo is Espanso's config folder ($expected)"
    }
    New-CheckResult $false ("This repo is in $RepoRoot, but Espanso reads $expected.`n" +
        'Back that folder up, clone the repo into it, and run install.ps1 from there.')
}

function Test-EspansoCli {
    if (Test-Path $EspansoCmd) { return New-CheckResult $true "Espanso found ($EspansoCmd)" }
    New-CheckResult $false ("Espanso not found at $EspansoCmd.`n" +
        'Install it for your user from https://espanso.org/install/ (the :gpt: form calls espanso.cmd there).')
}

function Get-PythonInfo([string[]]$Command) {
    $executable = $Command[0]
    if (-not (Get-Command $executable -ErrorAction SilentlyContinue)) { return $null }
    $probe = 'import sys; print(sys.executable); print(*sys.version_info[:3], sep=chr(46))'
    $arguments = @($Command | Select-Object -Skip 1) + @('-c', $probe)
    $lines = @(& $executable @arguments 2>$null)
    if ($LASTEXITCODE -ne 0 -or $lines.Count -lt 2) { return $null }
    [pscustomobject]@{ Path = $lines[0]; Version = [version]$lines[1] }
}

function Find-Python {
    foreach ($candidate in 'py -3', 'python', 'python3') {
        $info = Get-PythonInfo ($candidate -split ' ')
        if ($info -and $info.Version -ge $MinPythonVersion) { return $info }
    }
    $null
}

function Initialize-Venv([string]$RepoRoot) {
    $venvDir = Join-Path $RepoRoot '.venv'
    $existing = Get-PythonInfo @(Join-Path $venvDir 'Scripts\python.exe')
    if ($existing -and $existing.Version -ge $MinPythonVersion) {
        return New-CheckResult $true "Using .venv (Python $($existing.Version))"
    }
    $python = Find-Python
    if (-not $python) {
        return New-CheckResult $false ("Python $MinPythonVersion or newer not found.`n" +
            'Install it from https://www.python.org/downloads/ and run install.ps1 again.')
    }
    & $python.Path -m venv --clear $venvDir | Out-Host
    if ($LASTEXITCODE -ne 0) { return New-CheckResult $false 'Could not create .venv; the error is printed above.' }
    New-CheckResult $true "Created .venv with Python $($python.Version)"
}

function Install-Requirements([string]$VenvPython, [string]$RepoRoot) {
    & $VenvPython -m pip install --disable-pip-version-check --quiet -r (Join-Path $RepoRoot 'requirements.txt') | Out-Host
    if ($LASTEXITCODE -eq 0) { return New-CheckResult $true 'Dependencies installed (requirements.txt)' }
    New-CheckResult $false 'pip install failed; the error is printed above.'
}

function Get-ShushProxyUrl([string]$RepoRoot) {
    if ($env:SHUSH_PROXY_URL) { return $env:SHUSH_PROXY_URL.TrimEnd('/') }
    $envFile = Join-Path $RepoRoot 'scripts\.env'
    if (-not (Test-Path $envFile)) { return $DefaultProxyUrl }
    $line = Get-Content $envFile | Where-Object { $_ -match '^\s*SHUSH_PROXY_URL\s*=' } | Select-Object -Last 1
    if (-not $line) { return $DefaultProxyUrl }
    ($line -split '=', 2)[1].Trim().Trim('"', "'").TrimEnd('/')
}

function Read-ErrorCode([string]$Body) {
    try { [string](ConvertFrom-Json $Body -ErrorAction Stop).error.code } catch { '' }
}

function Invoke-ProxyProbe([string]$Url) {
    $client = New-Object System.Net.Http.HttpClient
    $client.Timeout = [TimeSpan]::FromSeconds(20)
    try {
        $response = $client.GetAsync($Url).GetAwaiter().GetResult()
        $body = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        [pscustomobject]@{ Status = [int]$response.StatusCode; ErrorCode = Read-ErrorCode $body }
    } catch {
        [pscustomobject]@{ Status = 0; ErrorCode = '' }
    } finally {
        $client.Dispose()
    }
}

function Test-ShushProxy([string]$ProxyUrl) {
    if ((Invoke-ProxyProbe "$ProxyUrl/").Status -ne 0) {
        return New-CheckResult $true "shush proxy is running ($ProxyUrl)"
    }
    if (-not (Get-Command shush -ErrorAction SilentlyContinue)) {
        return New-CheckResult $false ("shush isn't installed. It holds the API keys; no AI feature works without it.`n" +
            "Install: git clone https://github.com/latranchee/shush, add that folder to your PATH, then: shush proxy start")
    }
    New-CheckResult $false ("shush proxy isn't running at $ProxyUrl. Start it: shush proxy start`n" +
        "(keep that window open, or run it as a service with shush's install_proxy_service.ps1)")
}

function Get-MissingProviderFix($Provider) {
    $entry = '"{0}": {{ "secret": "{1}", "auth": "bearer", "base_url": "{2}", "max_body_bytes": {3} }}' -f
        $Provider.Name, $Provider.Secret, $Provider.BaseUrl, $Provider.MaxBodyBytes
    "shush has no '$($Provider.Name)' provider. Add this under `"providers`" in shush's proxy.json`n" +
        "(next to secret_manager.ps1; the proxy reloads it by itself):`n  $entry"
}

function Get-ProviderFix($Provider, $Probe) {
    $secret = $Provider.Secret
    if ($Probe.Status -eq 200) { return $null }
    if ($Probe.ErrorCode -eq 'PROVIDER_NOT_FOUND') { return Get-MissingProviderFix $Provider }
    if ($Probe.ErrorCode -eq 'SECRET_UNAVAILABLE') { return "No '$secret' key in the shush vault. Store it: shush set $secret" }
    if ($Probe.Status -in 401, 403) { return "The key in '$secret' was rejected. Replace it: shush set $secret --force" }
    if ($Probe.ErrorCode -eq 'model_not_found') {
        return "The '$secret' key can't use $DefaultModel. Use a key from an OpenAI project that has it."
    }
    "Unexpected reply through shush '$($Provider.Name)' (HTTP $($Probe.Status) $($Probe.ErrorCode)). Check the shush proxy log."
}

function Test-ShushProvider([string]$ProxyUrl, $Provider) {
    $probe = Invoke-ProxyProbe "$ProxyUrl/$($Provider.Name)$($Provider.ProbePath)"
    $fix = Get-ProviderFix $Provider $probe
    if ($fix) { return New-CheckResult $false $fix }
    New-CheckResult $true "shush provider '$($Provider.Name)' works (key '$($Provider.Secret)')"
}

function Test-Microphone([string]$VenvPython) {
    $name = & $VenvPython -c "import sounddevice; print(sounddevice.query_devices(kind='input')['name'])" 2>$null
    if ($LASTEXITCODE -eq 0 -and $name) { return New-CheckResult $true "Microphone: $name" }
    New-CheckResult $false 'No microphone found. F8 dictation needs one (Settings > System > Sound > Input).'
}

function New-DictationShortcut([string]$RepoRoot) {
    $shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($ShortcutPath)
    $shortcut.TargetPath = Join-Path $RepoRoot '.venv\Scripts\pythonw.exe'
    $shortcut.Arguments = '"' + (Join-Path $RepoRoot 'scripts\push_to_talk.py') + '"'
    $shortcut.WorkingDirectory = Join-Path $RepoRoot 'scripts'
    $shortcut.Description = $ShortcutDescription
    $shortcut.Save()
    New-CheckResult $true "Startup shortcut: $ShortcutPath (starts F8 dictation at login)"
}

function Get-DictationProcesses {
    @(Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | Where-Object { $_.CommandLine -like '*push_to_talk*' })
}

function Restart-DictationDaemon {
    $running = Get-DictationProcesses
    $running | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    $running | ForEach-Object { Wait-Process -Id $_.ProcessId -Timeout 5 -ErrorAction SilentlyContinue }
    Start-Process $ShortcutPath
    Start-Sleep -Seconds 3
    if ((Get-DictationProcesses).Count -eq 0) {
        return New-CheckResult $false 'The F8 daemon quit right after starting. See logs\push_to_talk.log.'
    }
    $verb = if ($running.Count) { 'restarted' } else { 'started' }
    New-CheckResult $true "F8 dictation daemon $verb"
}

function Restart-Espanso {
    # Start-Process, not &: the new espanso daemon would inherit redirected output pipes and hang this script.
    # Reading Handle up front keeps ExitCode readable after the process exits.
    $process = Start-Process $EspansoCmd -ArgumentList 'restart' -WindowStyle Hidden -PassThru
    $null = $process.Handle
    if ($process.WaitForExit(30000) -and $process.ExitCode -eq 0) { return New-CheckResult $true 'Espanso restarted' }
    New-CheckResult $false 'Could not restart Espanso. Run: espanso restart'
}

function Install-EspansoSection([string]$RepoRoot) {
    Write-Heading 'Espanso'
    Show-Result (Test-ConfigLocation $RepoRoot)
    Show-Result (Test-EspansoCli)
}

function Install-PythonSection([string]$RepoRoot) {
    Write-Heading 'Python'
    $venv = Show-Result (Initialize-Venv $RepoRoot)
    if ($venv.Ok) { Show-Result (Install-Requirements (Join-Path $RepoRoot '.venv\Scripts\python.exe') $RepoRoot) }
}

function Install-ShushSection([string]$RepoRoot, [bool]$WithDictation) {
    Write-Heading 'API keys (shush)'
    $proxyUrl = Get-ShushProxyUrl $RepoRoot
    $proxy = Show-Result (Test-ShushProxy $proxyUrl)
    if (-not $proxy.Ok) { return }
    Show-Result (Test-ShushProvider $proxyUrl $OpenAiProvider)
    if ($WithDictation) { Show-Result (Test-ShushProvider $proxyUrl $XaiProvider) }
}

function Install-DictationSection([string]$RepoRoot) {
    Write-Heading 'F8 dictation'
    Show-Result (Test-Microphone (Join-Path $RepoRoot '.venv\Scripts\python.exe'))
    Show-Result (New-DictationShortcut $RepoRoot)
    Show-Result (Restart-DictationDaemon)
}

function Install-ReloadSection {
    Write-Heading 'Reload'
    Show-Result (Restart-Espanso)
}

function Get-FixCount($Results) {
    @($Results | Where-Object { -not $_.Ok }).Count
}

function Write-Summary($Results, [bool]$WithDictation) {
    $fixes = Get-FixCount $Results
    Write-Host ''
    if ($fixes -gt 0) {
        Write-Host "$fixes thing(s) to fix, marked [fix] above. Then run .\install.ps1 again." -ForegroundColor Yellow
        return
    }
    $dictation = if ($WithDictation) { ' Tap F8 to dictate.' } else { '' }
    Write-Host "All set. Type :gpt:, :rephrase: or :support: in any app.$dictation" -ForegroundColor Green
}

function Install-EspansoGpt([string]$RepoRoot, [bool]$WithDictation) {
    $espanso = @(Install-EspansoSection $RepoRoot)
    $python = @(Install-PythonSection $RepoRoot)
    $shush = @(Install-ShushSection $RepoRoot $WithDictation)
    $pythonReady = (Get-FixCount $python) -eq 0
    $dictation = @()
    if ($WithDictation -and $pythonReady) { $dictation = @(Install-DictationSection $RepoRoot) }
    $reload = @()
    if ($pythonReady -and (Get-FixCount $espanso) -eq 0) { $reload = @(Install-ReloadSection) }
    $results = $espanso + $python + $shush + $dictation + $reload
    Write-Summary $results $WithDictation
    Get-FixCount $results
}

$fixCount = Install-EspansoGpt -RepoRoot (Resolve-Path $PSScriptRoot).Path -WithDictation (-not $SkipDictation)
exit ([int]($fixCount -gt 0))
