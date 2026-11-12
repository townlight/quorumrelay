$ErrorActionPreference = 'Stop'
if (-not $env:CIVIC_CONNECTOR_URL -or -not $env:CIVIC_CONNECTOR_TOKEN) { throw 'Set explicit CIVIC_CONNECTOR_URL and CIVIC_CONNECTOR_TOKEN.' }
$base = $env:CIVIC_CONNECTOR_URL.TrimEnd('/')
$headers = @{Authorization="Bearer $env:CIVIC_CONNECTOR_TOKEN"}
function Invoke-Connector([string]$Operation, $Request) {
  return Invoke-RestMethod -Method Post -Uri "$base/v1/operations/$Operation" -Headers $headers `
    -ContentType 'application/json' -Body ($Request | ConvertTo-Json -Depth 100 -Compress)
}
$capture = '[{"EventId":7,"EventBodyName":"Council","EventDate":"2026-11-11T00:00:00","EventTime":"7:00 PM","EventRowVersion":"r7"}]'
$discovered = Invoke-Connector discover @{
  source=@{provider='legistar';url='https://mock-city.legistar.com/Calendar.aspx';input_format='legistar-events-json'}
  content_base64=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($capture))
}
if ($discovered.status -ne 'partial') { throw 'Saved discovery must remain partial.' }
$preview = Invoke-Connector import_preview @{result=$discovered}
$imported = Invoke-Connector import_bundle @{result=$discovered;persist=$true}
$found = Invoke-Connector search @{query=@{terms=@('Council')}}
$exported = Invoke-Connector export @{bundle=$imported.data.bundle;format='zip';stream=$true}
$response = Invoke-WebRequest -Uri "$base$($exported.data.download_path)" -Headers $headers
@{mode='synthetic';live_acceptance='NOT_RUN';hits=$found.data.hits.Count;preview_persisted=$preview.data.persisted;download_bytes=$response.RawContentLength} |
  ConvertTo-Json -Compress
