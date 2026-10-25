# Install the generated packages shipped in this checkout. No Python required.
[CmdletBinding()]
param(
    [switch]$IncludePrompts,
    [switch]$RetireMigrated,
    [string]$SkillsDir = $env:CODEX_SKILLS_DIR,
    [string]$CodexHome = $env:CODEX_HOME
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if (-not $SkillsDir) { $SkillsDir = Join-Path $env:USERPROFILE '.agents/skills' }
if (-not $CodexHome) { $CodexHome = Join-Path $env:USERPROFILE '.codex' }
$SkillsDir = [IO.Path]::GetFullPath($SkillsDir)
$CodexHome = [IO.Path]::GetFullPath($CodexHome)
$PromptsDir = Join-Path $CodexHome 'prompts'
$BackupRoot = Join-Path $CodexHome ('backups/ai-berkshire-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
$Utf8 = New-Object System.Text.UTF8Encoding($false)

function Assert-ChildPath([string]$Path, [string]$Parent) {
    $full = [IO.Path]::GetFullPath($Path)
    $prefix = [IO.Path]::GetFullPath($Parent).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is outside the expected directory: $full (parent: $Parent)"
    }
}

function Test-Overlap([string]$Left, [string]$Right) {
    $a = [IO.Path]::GetFullPath($Left).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    $b = [IO.Path]::GetFullPath($Right).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    return $a.StartsWith($b, [StringComparison]::OrdinalIgnoreCase) -or $b.StartsWith($a, [StringComparison]::OrdinalIgnoreCase)
}

function Assert-NoLinks([string]$Path, [switch]$Recurse) {
    # Check ancestors as well: a lexical prefix does not protect against junctions.
    $cursor = [IO.Path]::GetFullPath($Path)
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Refusing to modify a symlink or junction: $cursor"
            }
        }
        $cursor = [IO.Path]::GetDirectoryName($cursor)
    }
    if ($Recurse -and (Test-Path -LiteralPath $Path -PathType Container)) {
        foreach ($item in Get-ChildItem -LiteralPath $Path -Recurse -Force) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Refusing to copy or move a linked entry: $($item.FullName)"
            }
        }
    }
}

function Get-ContentHash([string]$Path) {
    $sha = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($Path)
    try { return [BitConverter]::ToString($sha.ComputeHash($stream)) }
    finally { $stream.Dispose(); $sha.Dispose() }
}

function Get-Fingerprint([string]$Path) {
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        return Get-ContentHash $Path
    }
    $entries = @(foreach ($file in Get-ChildItem -LiteralPath $Path -Recurse -File -Force | Sort-Object FullName) {
        $relative = $file.FullName.Substring($Path.TrimEnd([IO.Path]::DirectorySeparatorChar).Length)
        $relative + ':' + (Get-ContentHash $file.FullName)
    })
    return ($entries -join "`n")
}

function Backup-Existing([string]$Path, [string]$Parent, [string]$Category) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    Assert-ChildPath $Path $Parent
    Assert-NoLinks $Path -Recurse
    $destination = Join-Path (Join-Path $BackupRoot $Category) (Split-Path $Path -Leaf)
    Assert-ChildPath $destination $BackupRoot
    Assert-NoLinks $destination
    if (Test-Path -LiteralPath $destination) { throw "Backup already exists: $destination" }
    $before = Get-Fingerprint $Path
    New-Item -ItemType Directory -Path (Split-Path $destination -Parent) -Force | Out-Null
    Move-Item -LiteralPath $Path -Destination $destination
    if ((Get-Fingerprint $destination) -cne $before) { throw "Backup verification failed: $destination" }
    Write-Host "Backed up: $Path -> $destination"
}

try {
    $packages = @(Get-ChildItem -LiteralPath (Join-Path $Root 'codex-skills') -Directory | Where-Object {
        Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md') -PathType Leaf
    })
    if (-not $packages.Count) { throw 'No generated Codex skills found in this checkout.' }
    $prompts = @()
    if ($IncludePrompts) {
        $prompts = @(Get-ChildItem -LiteralPath (Join-Path $Root 'codex-prompts') -Filter '*.md' -File)
        if (-not $prompts.Count) { throw 'No generated Codex prompts found in this checkout.' }
        foreach ($prompt in $prompts) {
            if ($prompt.BaseName -notin $packages.Name) { throw "Prompt has no matching skill: $($prompt.Name)" }
        }
    }

    # Preflight every path before replacing anything. Never install into sources.
    foreach ($path in @($SkillsDir, $PromptsDir, $BackupRoot)) {
        if ((Test-Overlap $path (Join-Path $Root 'codex-skills')) -or
            (Test-Overlap $path (Join-Path $Root 'codex-prompts'))) {
            throw "Installation directory overlaps the checked-in packages: $path"
        }
        Assert-NoLinks $path
    }
    if ((Test-Overlap $SkillsDir $PromptsDir) -or (Test-Overlap $SkillsDir $BackupRoot) -or
        (Test-Overlap $PromptsDir $BackupRoot)) {
        throw 'Skills, prompts, and backup directories must not overlap.'
    }
    foreach ($package in $packages) {
        Assert-NoLinks $package.FullName -Recurse
        Assert-NoLinks (Join-Path $SkillsDir $package.Name) -Recurse
    }
    foreach ($prompt in $prompts) {
        Assert-NoLinks $prompt.FullName
        Assert-NoLinks (Join-Path $PromptsDir $prompt.Name)
    }

    New-Item -ItemType Directory -Path $SkillsDir -Force | Out-Null
    foreach ($package in $packages) {
        $target = Join-Path $SkillsDir $package.Name
        Assert-ChildPath $target $SkillsDir
        if ((Test-Path -LiteralPath $target -PathType Container) -and
            (Get-Fingerprint $target) -ceq (Get-Fingerprint $package.FullName)) { continue }
        Backup-Existing $target $SkillsDir 'skills'
        Copy-Item -LiteralPath $package.FullName -Destination $target -Recurse
        if ((Get-Fingerprint $target) -cne (Get-Fingerprint $package.FullName)) { throw "Skill verification failed: $target" }
    }
    Write-Host "Installed and verified $($packages.Count) Codex skills in $SkillsDir"

    if ($IncludePrompts) {
        New-Item -ItemType Directory -Path $PromptsDir -Force | Out-Null
        foreach ($prompt in $prompts) {
            $target = Join-Path $PromptsDir $prompt.Name
            Assert-ChildPath $target $PromptsDir
            # Bind the wrapper to the installed skill, including non-default paths.
            # Custom prompts expand dollar signs, so escape dollars in local paths.
            $skillPath = (Join-Path $SkillsDir ($prompt.BaseName + '/SKILL.md')).Replace('\', '/').Replace('$', '$$')
            $content = [IO.File]::ReadAllText($prompt.FullName, $Utf8)
            $content = $content.Replace('User arguments:', ('Installed skill file: ' + $skillPath + "`n`nUser arguments:"))
            if ((Test-Path -LiteralPath $target -PathType Leaf) -and
                [IO.File]::ReadAllText($target, $Utf8) -ceq $content) { continue }
            Backup-Existing $target $PromptsDir 'prompts'
            [IO.File]::WriteAllText($target, $content, $Utf8)
            if ([IO.File]::ReadAllText($target, $Utf8) -cne $content) { throw "Prompt verification failed: $target" }
        }
        Write-Host "Installed and verified $($prompts.Count) slash prompts in $PromptsDir"
    }

    # Retire only recognized copies of these workflows, after replacements verify.
    $retired = 0
    $legacyRoots = @((Join-Path $env:USERPROFILE '.agents/skills'), (Join-Path $CodexHome 'skills'), $SkillsDir) | Select-Object -Unique
    $rootIndex = 0
    foreach ($legacyRoot in $legacyRoots) {
        $rootIndex++
        foreach ($package in $packages) {
            $names = @('source-command-' + $package.Name)
            if ([IO.Path]::GetFullPath($legacyRoot) -ne $SkillsDir) { $names += $package.Name }
            foreach ($name in $names) {
                $legacy = Join-Path $legacyRoot $name
                $entry = Join-Path $legacy 'SKILL.md'
                if (-not (Test-Path -LiteralPath $entry -PathType Leaf)) { continue }
                $body = [IO.File]::ReadAllText($entry, $Utf8)
                $isMigrated = $name.StartsWith('source-command-') -and
                    ($body.Contains('Run the migrated source command') -or
                     $body.Contains('Use this skill when the user asks to run the migrated source command')) -and
                    $body.Contains($name)
                $isGenerated = -not $name.StartsWith('source-command-') -and
                    $body.Contains('This skill is generated from') -and $body.Contains('AI Berkshire')
                if (-not ($isMigrated -or $isGenerated)) { continue }
                if ($RetireMigrated) {
                    Backup-Existing $legacy $legacyRoot "retired-$rootIndex"
                    $retired++
                } else {
                    Write-Warning "Duplicate workflow retained: $legacy. Use -RetireMigrated to archive it."
                }
            }
        }
    }
    Write-Host "Archived $retired duplicate workflows. No unrelated skills were removed."
    if (Test-Path -LiteralPath $BackupRoot) { Write-Host "Backup directory: $BackupRoot" }
    Write-Host 'Reload the Codex extension / restart Codex, then start a new chat.'
    Write-Host 'Skill entry: $investment-research Tencent'
    if ($IncludePrompts) { Write-Host 'Slash entry: /prompts:investment-research Tencent' }
} catch {
    Write-Error "Codex installation failed: $_" -ErrorAction Continue
    exit 1
}
