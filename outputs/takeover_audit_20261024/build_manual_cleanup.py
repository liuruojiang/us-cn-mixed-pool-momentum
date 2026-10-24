"""Build the explicitly requested manual-only cleanup batch after audit completion.

This builder never deletes files. The batch has a read-only --preview mode.
Previously blocked targets and retained audit evidence are never eligible.
"""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/takeover_audit_20261024'
TARGETS = [OUT / 'scratch', OUT / 'data/scratch']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    old = json.loads((ROOT / 'outputs/audit_sync_20261024/cleanup_record.json').read_text(encoding='utf-8'))
    blocked = [Path(p).resolve() for p in old['targets']]
    blocked += [(ROOT / p).resolve() for p in old['previously_blocked']]
    tracked = set(subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode('utf-8').split('\0'))
    entries = []
    for target in TARGETS:
        target = target.resolve()
        assert target.is_relative_to(OUT) and target != OUT
        assert not any(target == b or target.is_relative_to(b) or b.is_relative_to(target) for b in blocked)
        if not target.exists():
            continue
        files, links = [], []
        for p in sorted(target.rglob('*')):
            if p.is_symlink() or p.is_junction():
                resolved = p.resolve(strict=True)
                assert resolved.is_relative_to(target) and resolved.is_dir(), p
                links.append({'path': p.relative_to(ROOT).as_posix(), 'target': resolved.relative_to(ROOT).as_posix()})
                continue
            if p.is_file():
                rel = p.relative_to(ROOT).as_posix()
                assert rel not in tracked, rel
                files.append({'path': rel, 'sha256': sha(p), 'bytes': p.stat().st_size})
        entries.append({'directory': target.relative_to(ROOT).as_posix(), 'files': files, 'links': links})
    plan = {'workspace': str(ROOT), 'targets': entries, 'previously_blocked_excluded': [str(p) for p in blocked],
            'file_count': sum(len(e['files']) for e in entries),
            'directory_link_count': sum(len(e['links']) for e in entries),
            'bytes': sum(f['bytes'] for e in entries for f in e['files']),
            'execution': 'manual only; preview verified by agent; no deletion by agent'}
    (OUT / 'manual_cleanup_plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    payload = r'''
$ErrorActionPreference = 'Stop'
try {
    $plan = ConvertFrom-Json @'
__PLAN__
'@
    $root = [IO.Path]::GetFullPath([string]$plan.workspace).TrimEnd('\')
    $scriptRoot = [IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($env:TAKEOVER_CLEANUP_SELF))
    if ($root -ne $scriptRoot) { throw 'Keep this batch in its original project root.' }
    function Get-Sha([string]$path) {
        $alg = [Security.Cryptography.SHA256]::Create()
        $stream = [IO.File]::OpenRead($path)
        try { return [BitConverter]::ToString($alg.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
        finally { $stream.Dispose(); $alg.Dispose() }
    }
    function Check-Path([string]$path) {
        $full = [IO.Path]::GetFullPath($path)
        if (-not $full.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "Outside workspace: $full" }
        $walk = $full
        while ($walk) {
            if (Test-Path -LiteralPath $walk) {
                if ((Get-Item -Force -LiteralPath $walk).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Reparse point rejected: $walk" }
            }
            $parent = [IO.Path]::GetDirectoryName($walk)
            if ($parent -eq $walk) { break }
            $walk = $parent
        }
        return $full
    }
    function Check-Link($link, [string]$dir) {
        $path = [IO.Path]::GetFullPath((Join-Path $root $link.path))
        if (-not $path.StartsWith($dir + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Link outside target.' }
        $null = Check-Path ([IO.Path]::GetDirectoryName($path))
        $item = Get-Item -LiteralPath $path -Force
        if (-not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or -not $item.PSIsContainer) { throw 'Expected directory link changed.' }
        $to = [string]@($item.Target)[0]
        if ($to.StartsWith('\\?\')) { $to = $to.Substring(4) }
        if (-not [IO.Path]::IsPathRooted($to)) { $to = Join-Path ([IO.Path]::GetDirectoryName($path)) $to }
        $to = Check-Path $to
        $expected = [IO.Path]::GetFullPath((Join-Path $root $link.target))
        if ($to -ne $expected -or -not $to.StartsWith($dir + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Directory link target changed.' }
        return $path
    }
    function Get-ItemsWithoutFollowingLinks([string]$dir) {
        foreach ($item in Get-ChildItem -LiteralPath $dir -Force) {
            $item
            if ($item.PSIsContainer -and -not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
                Get-ItemsWithoutFollowingLinks $item.FullName
            }
        }
    }
    function Check-Target($target) {
        $dir = Check-Path (Join-Path $root $target.directory)
        if (-not (Test-Path -LiteralPath $dir)) { return $false }
        $items = @(Get-ItemsWithoutFollowingLinks $dir)
        $links = @($items | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint })
        if ($links.Count -ne @($target.links).Count) { throw 'Directory link set changed.' }
        foreach ($link in $target.links) { $null = Check-Link $link $dir }
        foreach ($item in $items) {
            if (-not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { $null = Check-Path $item.FullName }
        }
        $actual = @($items | Where-Object { -not $_.PSIsContainer -and -not ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) })
        if ($actual.Count -ne @($target.files).Count) { throw "File set changed; stopped: $dir" }
        foreach ($f in $target.files) {
            $path = Check-Path (Join-Path $root $f.path)
            if (-not $path.StartsWith($dir + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Manifest scope mismatch.' }
            if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "File missing: $path" }
            if ((Get-Item -LiteralPath $path).Length -ne $f.bytes -or (Get-Sha $path) -ne $f.sha256) { throw "File changed; stopped: $path" }
        }
        return $true
    }
    $active = @()
    foreach ($target in $plan.targets) {
        if (Check-Target $target) { $active += $target; Write-Host ('READY: ' + $target.directory) }
        else { Write-Host ('ALREADY ABSENT: ' + $target.directory) }
    }
    Write-Host ('Previously blocked targets excluded: ' + @($plan.previously_blocked_excluded).Count)
    Write-Host ('Manifest file count: ' + $plan.file_count)
    Write-Host ('Verified internal directory links: ' + $plan.directory_link_count)
    if ($env:TAKEOVER_CLEANUP_MODE -eq '--preview') {
        Write-Host 'PREVIEW PASS. No backup, deletion, or filesystem mutation performed.'
        exit 0
    }
    if ($active.Count -eq 0) { Write-Host 'Nothing remains to clean.'; exit 0 }
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $backupDir = Check-Path (Join-Path $root '.codex_backups')
    $null = New-Item -ItemType Directory -Force -Path $backupDir
    $archive = Join-Path $backupDir ('manual_takeover_cleanup_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '_' + [Guid]::NewGuid().ToString('N') + '.zip')
    $zip = [IO.Compression.ZipFile]::Open($archive, [IO.Compression.ZipArchiveMode]::Create)
    try {
        $entry = $zip.CreateEntry('manual_cleanup_manifest.json')
        $writer = New-Object IO.StreamWriter($entry.Open(), [Text.Encoding]::UTF8)
        try { $writer.Write(($plan | ConvertTo-Json -Depth 20)) } finally { $writer.Dispose() }
        foreach ($target in $active) { foreach ($f in $target.files) {
            $null = [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, (Join-Path $root $f.path), $f.path, [IO.Compression.CompressionLevel]::Optimal)
        }}
    } finally { $zip.Dispose() }
    $zip = [IO.Compression.ZipFile]::OpenRead($archive)
    try {
        foreach ($target in $active) { foreach ($f in $target.files) {
            $entry = $zip.GetEntry($f.path)
            if ($null -eq $entry -or $entry.Length -ne $f.bytes) { throw 'Backup entry missing or size mismatch.' }
            $stream = $entry.Open(); $alg = [Security.Cryptography.SHA256]::Create()
            try { $hash = [BitConverter]::ToString($alg.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
            finally { $stream.Dispose(); $alg.Dispose() }
            if ($hash -ne $f.sha256) { throw 'Backup hash mismatch; no cleanup performed.' }
        }}
    } finally { $zip.Dispose() }
    # Revalidate the entire frozen scope after backup, before any removal.
    foreach ($target in $active) { if (-not (Check-Target $target)) { throw 'Target changed during backup.' } }
    Write-Host ('Verified recovery archive: ' + $archive)
    foreach ($target in $active) {
        $dir = Check-Path (Join-Path $root $target.directory)
        foreach ($link in $target.links) {
            $linkPath = Check-Link $link $dir
            # Non-recursive deletion removes this verified reparse point itself.
            [IO.Directory]::Delete($linkPath, $false)
        }
        Remove-Item -LiteralPath $dir -Recurse -Force
        if (Test-Path -LiteralPath $dir) { throw "Removal incomplete: $dir" }
        Write-Host ('REMOVED: ' + $target.directory)
    }
    Write-Host 'Cleanup complete. Regression tests, audit evidence and old blocked targets were retained.'
    exit 0
} catch {
    Write-Host ('STOPPED: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
'''.replace('__PLAN__', json.dumps(plan, ensure_ascii=False, indent=2))
    launcher = r'''@echo off
setlocal
set "TAKEOVER_CLEANUP_SELF=%~f0"
set "TAKEOVER_CLEANUP_MODE=%~1"
powershell.exe -NoLogo -NoProfile -Command "$s=[IO.File]::ReadAllText($env:TAKEOVER_CLEANUP_SELF,[Text.Encoding]::UTF8); $m='# TAKEOVER_PS_PAYLOAD'; Invoke-Expression ($s.Substring($s.LastIndexOf($m)+$m.Length))"
set "TAKEOVER_CLEANUP_EXIT=%ERRORLEVEL%"
if /I "%~1"=="--preview" exit /b %TAKEOVER_CLEANUP_EXIT%
echo.
echo Exit code: %TAKEOVER_CLEANUP_EXIT%
pause
exit /b %TAKEOVER_CLEANUP_EXIT%
# TAKEOVER_PS_PAYLOAD
'''
    batch = ROOT / 'cleanup_takeover_tests_20261024.bat'
    assert not batch.exists(), 'Refuse to overwrite an existing user batch'
    batch.write_bytes((launcher + payload).replace('\r\n', '\n').replace('\n', '\r\n').encode('utf-8'))
    print(json.dumps({'batch': str(batch), 'targets': len(entries), 'files': plan['file_count'], 'bytes': plan['bytes']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
