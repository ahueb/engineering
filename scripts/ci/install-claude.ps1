# Install Claude Code at the pinned version on Windows and verify the binary against the
# GPG-signed release manifest (gpg from Git for Windows).
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Version = (Get-Content "$Here\claude-version.txt" -Raw).Trim()
$Fpr = "31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE"
$Repo = "https://downloads.claude.ai/claude-code-releases"
$Tmp = Join-Path $env:TEMP ("claude-verify-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $Tmp | Out-Null
try {
    # gpg here is the MSYS build from Git for Windows, which reads paths in POSIX form
    # (C:\Users\x -> /c/Users/x; a Windows path is taken as relative). Every path handed to
    # gpg goes through ToMsys, and gpg's stderr is kept for the failure message.
    function ToMsys([string]$p) {
        $p = $p -replace '\\', '/'
        if ($p -match '^([A-Za-z]):/(.*)$') { return "/" + $Matches[1].ToLower() + "/" + $Matches[2] }
        return $p
    }
    $GnupgHomeWin = Join-Path $Tmp "gnupg"
    New-Item -ItemType Directory -Path $GnupgHomeWin | Out-Null
    $GnupgHome = ToMsys $GnupgHomeWin
    $env:GNUPGHOME = $GnupgHome
    $KeyPath = ToMsys "$Here\anthropic-release-key.asc"
    $gpgVersion = (& gpg --version 2>&1 | Select-Object -First 1)

    # 1. Key: the vendored key must carry the published fingerprint and must be the only
    #    primary key imported into this throwaway keyring.
    $importOut = & gpg --homedir $GnupgHome --batch --import $KeyPath 2>&1
    $fprs = @(& gpg --homedir $GnupgHome --batch --with-colons --fingerprint 2>&1 | ForEach-Object { "$_" })
    $pubCount = @($fprs | Where-Object { $_ -match "^pub:" }).Count
    if ($pubCount -ne 1) { throw "expected exactly one primary key in the keyring, found $pubCount ($gpgVersion; home $GnupgHome; import: $($importOut -join ' | '); list: $($fprs -join ' | '))" }
    if (-not ($fprs | Select-String -Pattern "^fpr:+${Fpr}:")) { throw "release key fingerprint mismatch" }

    # 2. Manifest: signature must verify against that key and be bound to the pinned fingerprint.
    Invoke-WebRequest -Uri "$Repo/$Version/manifest.json" -OutFile "$Tmp\manifest.json"
    Invoke-WebRequest -Uri "$Repo/$Version/manifest.json.sig" -OutFile "$Tmp\manifest.json.sig"
    $status = & gpg --homedir $GnupgHome --batch --status-fd 1 --verify (ToMsys "$Tmp\manifest.json.sig") (ToMsys "$Tmp\manifest.json") 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) { throw "manifest signature invalid for $Version" }
    if (-not ($status | Select-String -Pattern "^\[GNUPG:\] VALIDSIG .* $Fpr$")) { throw "manifest signature not bound to $Fpr" }
    if ($status | Select-String -Pattern "^\[GNUPG:\] (EXPKEYSIG|REVKEYSIG|KEYREVOKED|KEYEXPIRED|EXPSIG)") { throw "manifest signed by an expired or revoked key" }

    # 3. Download the platform binary named in the verified manifest directly (no convenience
    #    installer is executed) and verify its SHA256 and size against the manifest BEFORE the
    #    binary is placed anywhere or run.
    $Platform = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "win32-arm64" } else { "win32-x64" }
    $Manifest = Get-Content "$Tmp\manifest.json" -Raw | ConvertFrom-Json
    $BinaryName = $Manifest.platforms.$Platform.binary
    $Expected = ([string]$Manifest.platforms.$Platform.checksum).ToLower()
    $ExpectedSize = $Manifest.platforms.$Platform.size

    $DownloadPath = Join-Path $Tmp "claude.exe"
    Invoke-WebRequest -Uri "$Repo/$Version/$Platform/$BinaryName" -OutFile $DownloadPath

    $Actual = (Get-FileHash -Algorithm SHA256 -Path $DownloadPath).Hash.ToLower()
    $ActualSize = (Get-Item $DownloadPath).Length
    if ($Expected -ne $Actual -or $ExpectedSize -ne $ActualSize) {
        Remove-Item -Force $DownloadPath -ErrorAction SilentlyContinue
        throw "binary checksum/size mismatch: expected sha256=$Expected size=$ExpectedSize got sha256=$Actual size=$ActualSize"
    }

    $BinDir = Join-Path $env:USERPROFILE ".local\bin"
    New-Item -ItemType Directory -Path $BinDir -Force | Out-Null
    $Bin = Join-Path $BinDir "claude.exe"
    Move-Item -Force $DownloadPath $Bin

    Write-Output "claude $Version verified ($Platform, sha256 $Actual)"
    $VersionOutput = & $Bin --version
    if ($VersionOutput -notmatch [regex]::Escape($Version)) { throw "installer produced a different version" }
    Write-Output $VersionOutput
}
finally {
    Remove-Item -Recurse -Force $Tmp -ErrorAction SilentlyContinue
}
