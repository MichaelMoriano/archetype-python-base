$ErrorActionPreference = "Stop"
$env:SONAR_HOST_URL = "http://localhost:9000"
$env:PYTHONUTF8 = "1"

$secureToken = Read-Host "SonarQube analysis token" -AsSecureString
$env:SONAR_TOKEN = [System.Net.NetworkCredential]::new("", $secureToken).Password

$metadataFile = [System.IO.Path]::GetTempFileName()
try {
    uv run --locked pysonar --sonar-qualitygate-wait --sonar-scanner-metadata-filepath $metadataFile
    $scannerExitCode = $LASTEXITCODE

    if ($scannerExitCode -eq 0) {
        Write-Host "SonarQube analysis and Quality Gate passed."
        return
    }
    # Read only this run's metadata, never a previous analysis.
    $metadata = ConvertFrom-StringData ((Get-Content $metadataFile -Raw) + "`n")
    if (-not $metadata.ceTaskId) { throw "No analysis metadata; check scanner output (exit $scannerExitCode)." }
    try {
        $request = @{
            Headers = @{ Authorization = "Bearer $env:SONAR_TOKEN" }
            TimeoutSec = 15
            MaximumRedirection = 0
        }
        $taskId = [Uri]::EscapeDataString($metadata.ceTaskId)
        $task = Invoke-RestMethod "$env:SONAR_HOST_URL/api/ce/task?id=$taskId" @request
        if ($task.task.status -ne 'SUCCESS' -or -not $task.task.analysisId) { throw "Analysis unavailable." }
        $analysisId = [Uri]::EscapeDataString($task.task.analysisId)
        $result = Invoke-RestMethod "$env:SONAR_HOST_URL/api/qualitygates/project_status?analysisId=$analysisId" @request
        foreach ($condition in $result.projectStatus.conditions | Where-Object status -eq 'ERROR') {
            $label = $condition.metricKey
            $unit = if ($label -match 'coverage|density|hotspots_reviewed') { '%' } else { '' }
            if ($label -eq 'coverage') { $label = 'Coverage' }
            if ($label -eq 'new_coverage') { $label = 'New code coverage' }
            $required = switch ($condition.comparator) { 'LT' { '>=' }; 'GT' { '<=' }; default { '?' } }
            Write-Host "- ${label}: $($condition.actualValue)$unit; required $required $($condition.errorThreshold)$unit"
        }
    } catch {
        Write-Warning "Quality Gate details unavailable; check server access and token permissions."
    }
    throw "SonarQube analysis or Quality Gate failed. See $env:SONAR_HOST_URL/dashboard?id=Archetype-Python-Base"
} finally {
    $request = $null
    Remove-Item -LiteralPath $metadataFile -ErrorAction SilentlyContinue
    Remove-Item Env:SONAR_TOKEN -ErrorAction SilentlyContinue
    $secureToken.Dispose()
}
