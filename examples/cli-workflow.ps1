param([Parameter(Mandatory=$true)][string]$Database)
$ErrorActionPreference = 'Stop'
$capture = '[{"EventId":7,"EventBodyName":"Council","EventDate":"2026-11-11T00:00:00","EventTime":"7:00 PM","EventRowVersion":"r7"}]'
$request = @{
  source = @{provider='legistar';url='https://mock-city.legistar.com/Calendar.aspx';input_format='legistar-events-json'}
  bounds = @{date_from='2026-11-11';date_to='2026-11-11'}
  content_base64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($capture))
}
function Invoke-Connector([string]$Operation, $Request) {
  $wire = $Request | ConvertTo-Json -Depth 100 -Compress
  $output = $wire | python -m quorumrelay $Operation --database $Database
  if ($LASTEXITCODE -notin @(0,2)) { throw "Connector $Operation failed." }
  return $output | ConvertFrom-Json -Depth 100
}
$discovered = Invoke-Connector discover $request
if ($discovered.status -ne 'partial') { throw 'Saved discovery must remain partial.' }
$preview = Invoke-Connector import_preview @{result=$discovered}
$imported = Invoke-Connector import_bundle @{result=$discovered;persist=$true}
$found = Invoke-Connector search @{query=@{terms=@('Council')}}
$exported = Invoke-Connector export @{bundle=$imported.data.bundle;format='zip'}
if ($found.data.hits.Count -lt 1 -or $preview.data.persisted -or -not $imported.data.persisted) {
  throw 'Import/search acceptance failed.'
}
if ($exported.status -notin @('completed','partial')) { throw 'Export acceptance failed.' }
@{mode='synthetic';live_acceptance='NOT_RUN';hits=$found.data.hits.Count;preview_persisted=$preview.data.persisted;export=$exported.status} |
  ConvertTo-Json -Compress
