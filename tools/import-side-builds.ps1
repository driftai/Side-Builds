<#
.SYNOPSIS
Imports project folders into the Side-Builds repo without nested git metadata or bulky local output.

.EXAMPLE
.\tools\import-side-builds.ps1

.EXAMPLE
.\tools\import-side-builds.ps1 -Projects Agentic-scribe-notetaker -Commit -Push

.EXAMPLE
.\tools\import-side-builds.ps1 -MoveAfterCopy -Confirm
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$Source,
    [string]$Repo,
    [string[]]$Projects,
    [switch]$MoveAfterCopy,
    [switch]$Commit,
    [switch]$Push,
    [string]$CommitMessage = 'Import side builds'
)

$ErrorActionPreference = 'Stop'

$scriptRoot = if ($PSScriptRoot) {
    $PSScriptRoot
} else {
    Split-Path -Parent $MyInvocation.MyCommand.Path
}

if (-not $Source) {
    $Source = Join-Path $scriptRoot '..\..\Side-Builds-ToBePushed'
}

if (-not $Repo) {
    $Repo = Join-Path $scriptRoot '..'
}

function Resolve-ExistingPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Label path does not exist: $Path"
    }

    return (Resolve-Path -LiteralPath $Path).Path
}

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoPath,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & git -C $RepoPath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

$sourcePath = Resolve-ExistingPath -Path $Source -Label 'Source'
$repoPath = Resolve-ExistingPath -Path $Repo -Label 'Repo'

if (-not (Test-Path -LiteralPath (Join-Path $repoPath '.git'))) {
    throw "Repo path is not a git repository: $repoPath"
}

if ($Projects -and $Projects.Count -gt 0) {
    $projectDirs = foreach ($projectName in $Projects) {
        $projectPath = Join-Path $sourcePath $projectName
        if (-not (Test-Path -LiteralPath $projectPath -PathType Container)) {
            throw "Project does not exist under source path: $projectName"
        }
        Get-Item -LiteralPath $projectPath
    }
} else {
    $projectDirs = Get-ChildItem -LiteralPath $sourcePath -Directory
}

if (-not $projectDirs) {
    Write-Host "No project folders found in $sourcePath"
    exit 0
}

$excludeDirNames = @(
    '.git',
    'node_modules',
    'dist',
    'dist-ssr',
    '.next',
    '.vite',
    '.turbo',
    'coverage',
    'logs'
)

$excludeFileNames = @(
    '.env',
    '.env.*',
    '*.local',
    '*.log',
    'npm-debug.log*',
    'yarn-debug.log*',
    'yarn-error.log*',
    'pnpm-debug.log*',
    'lerna-debug.log*'
)

foreach ($project in $projectDirs) {
    $destination = Join-Path $repoPath $project.Name
    if (Test-Path -LiteralPath $destination) {
        throw "Destination already exists: $destination"
    }

    $robocopyArgs = @(
        $project.FullName,
        $destination,
        '/E',
        '/R:1',
        '/W:1',
        '/NFL',
        '/NDL',
        '/NP',
        '/NJH',
        '/NJS',
        '/XD'
    ) + $excludeDirNames + @('/XF') + $excludeFileNames

    & robocopy @robocopyArgs | Out-Host
    $copyExitCode = $LASTEXITCODE
    if ($copyExitCode -gt 7) {
        throw "robocopy failed for $($project.Name) with exit code $copyExitCode"
    }

    Write-Host "Imported $($project.Name)"

    if ($MoveAfterCopy) {
        if ($PSCmdlet.ShouldProcess($project.FullName, 'Remove source project after import')) {
            Remove-Item -LiteralPath $project.FullName -Recurse -Force
            Write-Host "Removed source copy: $($project.FullName)"
        }
    }
}

Invoke-Git -RepoPath $repoPath -Arguments @('status', '--short')

if ($Commit) {
    Invoke-Git -RepoPath $repoPath -Arguments @('add', '-A')
    $changes = & git -C $repoPath status --porcelain
    if ($LASTEXITCODE -ne 0) {
        throw "git status --porcelain failed with exit code $LASTEXITCODE"
    }

    if ($changes) {
        Invoke-Git -RepoPath $repoPath -Arguments @('commit', '-m', $CommitMessage)
    } else {
        Write-Host 'No changes to commit.'
    }
}

if ($Push) {
    Invoke-Git -RepoPath $repoPath -Arguments @('push', 'origin', 'main')
}
