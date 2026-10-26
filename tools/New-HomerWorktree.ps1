[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)]
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$')]
    [string]$Name,
    [ValidateSet('web','android')]
    [string]$Repository='web',
    [string]$Ref='HEAD',
    [string]$Branch
)
$ErrorActionPreference='Stop'
$workspaceRoot=[IO.Path]::GetFullPath('E:\HomerWorkspace')
$worktreeRoot=Join-Path $workspaceRoot 'worktrees'
$destination=[IO.Path]::GetFullPath((Join-Path $worktreeRoot $Name))
if([IO.Path]::GetDirectoryName($destination) -ne $worktreeRoot) {throw 'Worktree must be inside the fixed workspace'}
if(Test-Path -LiteralPath $destination) {throw ('Worktree already exists: '+$destination)}
foreach($parent in @($workspaceRoot,$worktreeRoot)) {
    if((Test-Path -LiteralPath $parent) -and ((Get-Item -LiteralPath $parent -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {throw 'Workspace parent must be a real directory'}
}
$repo=if($Repository -eq 'android') {Join-Path $workspaceRoot 'android'} else {Split-Path -Parent $PSScriptRoot}
& git -C $repo rev-parse --verify --quiet ($Ref+'^{commit}') | Out-Null
if($LASTEXITCODE -ne 0) {throw ('Unknown commit: '+$Ref)}
if($Branch) {
    & git check-ref-format --branch $Branch | Out-Null
    if($LASTEXITCODE -ne 0) {throw 'Invalid branch name'}
}
if($PSCmdlet.ShouldProcess($destination,('Create '+$Repository+' Git worktree from '+$Ref))) {
    New-Item -ItemType Directory -Path $worktreeRoot -Force | Out-Null
    if($Branch) {& git -C $repo worktree add -b $Branch $destination $Ref}
    else {& git -C $repo worktree add --detach $destination $Ref}
    if($LASTEXITCODE -ne 0) {throw 'Git worktree creation failed'}
    Write-Output $destination
}
