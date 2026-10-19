<#
.SYNOPSIS
    Starts the agent-hub server on Windows using PowerShell.

.DESCRIPTION
    Runs hub.py using the active Python interpreter. Pass any arguments directly to hub.py.

.EXAMPLE
    .\start_hub.ps1

.EXAMPLE
    .\start_hub.ps1 --port 8080 --public-url https://<laptop>.<tailnet>.ts.net
#>
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ArgsList
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
python "$scriptDir\hub.py" @ArgsList
