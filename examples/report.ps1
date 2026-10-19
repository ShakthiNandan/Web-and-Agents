<#
.SYNOPSIS
    Send a report or log event to agent-hub from PowerShell.

.EXAMPLE
    $env:AGENT_HUB_URL = "http://127.0.0.1:8080/<token>"
    .\report.ps1 -AgentId "my-agent" -Message "Task started" -Level "info"
#>
param(
    [Parameter(Mandatory = $true, Position = 0)][string]$AgentId,
    [Parameter(Mandatory = $false, Position = 1)][string]$Level = "info",
    [Parameter(Mandatory = $true, Position = 2)][string]$Message,
    [Parameter(Mandatory = $false)][string]$Url = $env:AGENT_HUB_URL
)

if (-not $Url) {
    Write-Error "AGENT_HUB_URL environment variable is not set and no -Url parameter was provided."
    exit 1
}

$payload = @{
    agent_id = $AgentId
    level = $Level
    msg = $Message
} | ConvertTo-Json

$targetUri = "$($Url.TrimEnd('/'))/report"
Invoke-RestMethod -Uri $targetUri -Method Post -ContentType "application/json" -Body $payload
