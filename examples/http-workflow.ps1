$ErrorActionPreference = 'Stop'
if (-not $env:CIVIC_CONNECTOR_URL -or -not $env:CIVIC_CONNECTOR_TOKEN) { throw 'Set explicit CIVIC_CONNECTOR_URL and CIVIC_CONNECTOR_TOKEN.' }
$base = $env:CIVIC_CONNECTOR_URL.TrimEnd('/')
$headers = @{Authorization="Bearer $env:CIVIC_CONNECTOR_TOKEN"}
function Invoke-Connector([string]$Operation, $Request) {
  $wire = $Request | ConvertTo-Json -Depth 100 -Compress
  $response = $wire | curl.exe --silent --show-error --fail-with-body --max-time 30 `
    --request POST --url "$base/v1/operations/$Operation" `
    --header "Authorization: Bearer $env:CIVIC_CONNECTOR_TOKEN" `
    --header 'Content-Type: application/json' --data-binary '@-'
  if ($LASTEXITCODE -ne 0) { throw "curl request failed for $Operation." }
  $result = $response | ConvertFrom-Json -Depth 100
  if ($result.status -notin @('completed','partial')) { throw "Operation $Operation did not succeed: $($result.status)" }
  return $result
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
if ($found.data.hits.Count -lt 1 -or $preview.data.persisted -or -not $imported.data.persisted) {
  throw 'Import/search acceptance failed.'
}
$exported = Invoke-Connector export @{bundle=$imported.data.bundle;format='zip';stream=$true}
$response = Invoke-WebRequest -Uri "$base$($exported.data.download_path)" -Headers $headers
$plan = Invoke-Connector plan_write @{
  source=@{provider='legistar';url='https://webapi.legistar.com/v1/mock-city/events';namespace='mock-city'}
  changes=@(@{key='curl-example';entity='event';operation='create';fields=@{EventDate='2026-11-11T00:00:00';EventBodyId=4}})
}
if ($plan.data.plan.mock -ne $true) { throw 'This example refuses non-mock writes.' }
$committed = Invoke-Connector commit_write @{plan_id=$plan.data.plan_id;plan_hash=$plan.data.plan_hash}
$receipt = Invoke-Connector receipt @{plan_id=$plan.data.plan_id}
if ($committed.data.mock -ne $true -or $receipt.data.mock -ne $true) { throw 'Expected a synthetic receipt.' }
@{mode='synthetic';live_acceptance='NOT_RUN';hits=$found.data.hits.Count;preview_persisted=$preview.data.persisted;download_bytes=$response.RawContentLength} |
  ConvertTo-Json -Compress
