# bdd-lib.ps1 – Gemeinsame BDD-Helfer für IaC4
# Konvention: Feature-Skripte in scripts/bdd/*.bdd.ps1, Testkatalog in qa/bdd-testkonzept.md
# Ausführung: GH Runner (ubuntu-latest, pwsh), nie lokal (Zugriffs-Design)

$global:BDD_PASS = 0
$global:BDD_FAIL = 0
$global:BDD_FAILURES = @()

function Given([string]$desc) {
    Write-Host "  Given  $desc" -ForegroundColor DarkGray
}
function When([string]$desc) {
    Write-Host "  When   $desc" -ForegroundColor DarkGray
}
function Then-True([string]$desc, [bool]$cond, [string]$detail = "") {
    if ($cond) {
        $global:BDD_PASS++
        Write-Host "  ✅ Then $desc" -ForegroundColor Green
    }
    else {
        $global:BDD_FAIL++
        $global:BDD_FAILURES += $desc
        Write-Host "  ❌ Then $desc" -ForegroundColor Red
        if ($detail) { Write-Host "        Detail: $detail" -ForegroundColor DarkRed }
    }
}
function Then-ExitCode([string]$desc, [int]$code, [int]$expected = 0) {
    Then-True $desc ($code -eq $expected) "Exit-Code: $code (erwartet: $expected)"
}
function Invoke-SSH([string]$cmd, [string]$user, [string]$ip, [string]$key, [int]$timeoutSec = 10) {
    $out = ssh -i $key -o StrictHostKeyChecking=accept-new -o ConnectTimeout=$timeoutSec `
        -o LogLevel=ERROR "$user@$ip" $cmd 2>&1
    return @{ ExitCode = $LASTEXITCODE; Output = ($out -join "`n") }
}
function Test-SshPortClosed([string]$user, [string]$ip, [string]$key) {
    # Erwartet: SSH-Port dicht (Verbindung schlägt fehl)
    $null = ssh -i $key -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 `
        -o LogLevel=ERROR "$user@$ip" "true" 2>$null
    return ($LASTEXITCODE -ne 0)
}
