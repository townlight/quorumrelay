param(
    [string]$OutDir = (Get-Location).Path,
    [string]$ValidateCreate = '',
    [string]$ValidateUpdate = ''
)

$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Data
Add-Type -AssemblyName System.Xml

function New-MeetingDataSet {
    $ds = New-Object System.Data.DataSet 'DB_1_0'
    $ds.Namespace = 'http://tempuri.org/DB_1_0.xsd'

    $meeting = New-Object System.Data.DataTable 'Meeting'
    [void]$meeting.Columns.Add('MeetingID', [int])
    [void]$meeting.Columns.Add('MeetingDate', [datetime])
    [void]$meeting.Columns.Add('ResolutionDueDate', [datetime])
    [void]$meeting.Columns.Add('MeetingTypeID', [int])
    [void]$meeting.Columns.Add('MeetingLocationID', [int])
    [void]$meeting.Columns.Add('MeetingStatusID', [System.Byte])
    [void]$meeting.Columns.Add('DepartmentID', [int])
    [void]$meeting.Columns.Add('TimestampStart', [datetime])
    [void]$meeting.Columns.Add('TimestampStartDelta', [int])
    [void]$meeting.Columns.Add('UnknownMeeting', [string])
    $meeting.Columns['MeetingID'].AutoIncrement = $true
    $meeting.Columns['MeetingID'].AutoIncrementSeed = -1
    $meeting.Columns['MeetingID'].AutoIncrementStep = -1
    $meeting.Columns['MeetingID'].ReadOnly = $true
    $meeting.Columns['TimestampStart'].AllowDBNull = $true
    $meeting.Columns['TimestampStartDelta'].DefaultValue = 0
    $meeting.Columns['MeetingDate'].DateTimeMode = [System.Data.DataSetDateTime]::UnspecifiedLocal
    $meeting.Columns['ResolutionDueDate'].DateTimeMode = [System.Data.DataSetDateTime]::UnspecifiedLocal
    $meeting.Columns['TimestampStart'].DateTimeMode = [System.Data.DataSetDateTime]::UnspecifiedLocal
    $meeting.PrimaryKey = @($meeting.Columns['MeetingID'])
    [void]$ds.Tables.Add($meeting)

    $unknown = New-Object System.Data.DataTable 'UnknownRow'
    [void]$unknown.Columns.Add('UnknownID', [int])
    [void]$unknown.Columns.Add('Payload', [string])
    $unknown.PrimaryKey = @($unknown.Columns['UnknownID'])
    [void]$ds.Tables.Add($unknown)

    $meetingDate = [datetime]::SpecifyKind([datetime]'2026-11-17T09:00:00', [System.DateTimeKind]::Unspecified)
    $resolutionDue = [datetime]::SpecifyKind([datetime]'2026-11-17T09:00:00', [System.DateTimeKind]::Unspecified)
    $timestampStart = [datetime]::SpecifyKind([datetime]'2026-11-17T17:00:00', [System.DateTimeKind]::Unspecified)
    [void]$meeting.Rows.Add(501, $meetingDate, $resolutionDue, 3, 4, [byte]10, 2, $timestampStart, 0, 'keep-meeting-unknown')
    [void]$unknown.Rows.Add(1, 'keep-unknown-row')
    $ds.AcceptChanges()
    return $ds
}

function Get-InlineSchemaElement($dataSet) {
    $sw = New-Object System.IO.StringWriter
    $settings = New-Object System.Xml.XmlWriterSettings
    $settings.OmitXmlDeclaration = $true
    $settings.Indent = $true
    $writer = [System.Xml.XmlWriter]::Create($sw, $settings)
    $dataSet.WriteXml($writer, [System.Data.XmlWriteMode]::WriteSchema)
    $writer.Close()
    $doc = New-Object System.Xml.XmlDocument
    $doc.PreserveWhitespace = $true
    $doc.LoadXml($sw.ToString())
    foreach ($child in $doc.DocumentElement.ChildNodes) {
        if ($child.NodeType -eq 'Element' -and $child.LocalName -eq 'schema' -and $child.NamespaceURI -eq 'http://www.w3.org/2001/XMLSchema') {
            return $child
        }
    }
    throw 'The DataSet did not produce an inline XML schema.'
}

function Write-BaselineSoapResponse($dataSet, $path) {
    $schema = Get-InlineSchemaElement $dataSet
    $swDiff = New-Object System.IO.StringWriter
    $settingsDiff = New-Object System.Xml.XmlWriterSettings
    $settingsDiff.OmitXmlDeclaration = $true
    $settingsDiff.Indent = $true
    $writerDiff = [System.Xml.XmlWriter]::Create($swDiff, $settingsDiff)
    $dataSet.WriteXml($writerDiff, [System.Data.XmlWriteMode]::DiffGram)
    $writerDiff.Close()
    $docDiff = New-Object System.Xml.XmlDocument
    $docDiff.PreserveWhitespace = $true
    $docDiff.LoadXml($swDiff.ToString())
    $diffgram = $docDiff.DocumentElement

    $settings2 = New-Object System.Xml.XmlWriterSettings
    $settings2.Indent = $true
    $settings2.OmitXmlDeclaration = $false
    $writer2 = [System.Xml.XmlWriter]::Create($path, $settings2)
    $writer2.WriteStartDocument()
    $writer2.WriteStartElement('soap', 'Envelope', 'http://schemas.xmlsoap.org/soap/envelope/')
    $writer2.WriteStartElement('soap', 'Body', 'http://schemas.xmlsoap.org/soap/envelope/')
    $writer2.WriteStartElement('MeetingGetResponse', 'http://tempuri.org/MinuteTraqService/Data_1_0')
    $writer2.WriteStartElement('MeetingGetResult', 'http://tempuri.org/MinuteTraqService/Data_1_0')
    $schema.WriteTo($writer2)
    $diffgram.WriteTo($writer2)
    $writer2.WriteEndElement()
    $writer2.WriteEndElement()
    $writer2.WriteEndElement()
    $writer2.WriteEndElement()
    $writer2.WriteEndDocument()
    $writer2.Close()
}

function Get-SoapDataSetNode($path) {
    $doc = New-Object System.Xml.XmlDocument
    $doc.Load($path)
    $nodes = $doc.GetElementsByTagName('ds')
    if ($nodes.Count -ne 1) {
        throw 'Expected exactly one ds element in the outbound request.'
    }
    return $nodes[0]
}

function Read-OutboundDataSet($path) {
    $dsNode = Get-SoapDataSetNode $path
    $sw = New-Object System.IO.StringWriter
    $writer = [System.Xml.XmlWriter]::Create($sw)
    $dsNode.WriteTo($writer)
    $writer.Close()
    $doc = New-Object System.Xml.XmlDocument
    $doc.PreserveWhitespace = $true
    $doc.LoadXml($sw.ToString())
    $schemaNode = $null
    $diffgramNode = $null
    foreach ($child in $doc.DocumentElement.ChildNodes) {
        if ($child.NodeType -ne 'Element') { continue }
        if ($child.LocalName -eq 'schema' -and $child.NamespaceURI -eq 'http://www.w3.org/2001/XMLSchema') {
            $schemaNode = $child
        }
        elseif ($child.LocalName -eq 'diffgram' -and $child.NamespaceURI -eq 'urn:schemas-microsoft-com:xml-diffgram-v1') {
            $diffgramNode = $child
        }
    }
    if ($null -eq $schemaNode) { throw 'The outbound ds contains no inline schema.' }
    if ($null -eq $diffgramNode) { throw 'The outbound ds contains no diffgram.' }

    $ds = New-Object System.Data.DataSet
    $swSchema = New-Object System.IO.StringWriter
    $writerSchema = [System.Xml.XmlWriter]::Create($swSchema)
    $schemaNode.WriteTo($writerSchema)
    $writerSchema.Close()
    $readerSchema = New-Object System.IO.StringReader($swSchema.ToString())
    $xmlReaderSchema = [System.Xml.XmlReader]::Create($readerSchema)
    try {
        $ds.ReadXmlSchema($xmlReaderSchema)
    }
    finally {
        $xmlReaderSchema.Close()
    }
    $ds.EnforceConstraints = $false

    $swDiff = New-Object System.IO.StringWriter
    $writerDiff = [System.Xml.XmlWriter]::Create($swDiff)
    $diffgramNode.WriteTo($writerDiff)
    $writerDiff.Close()
    $readerDiff = New-Object System.IO.StringReader($swDiff.ToString())
    $xmlReaderDiff = [System.Xml.XmlReader]::Create($readerDiff)
    try {
        [void]$ds.ReadXml($xmlReaderDiff, [System.Data.XmlReadMode]::DiffGram)
    }
    finally {
        $xmlReaderDiff.Close()
    }
    return $ds
}

function Get-RowCount($table) {
    if ($null -eq $table) { return 0 }
    return $table.Rows.Count
}

function Validate-CreateRequest($path) {
    $ds = Read-OutboundDataSet $path
    if (-not $ds.HasChanges()) { throw 'The outbound create ds contains no changes.' }
    $inserted = $ds.GetChanges([System.Data.DataRowState]::Added)
    if ($null -eq $inserted) { throw 'The outbound create ds contains no inserted rows.' }
    $count = 0
    foreach ($table in $inserted.Tables) { $count += $table.Rows.Count }
    if ($count -ne 1) { throw 'Expected exactly one inserted row.' }
    $meeting = $inserted.Tables['Meeting']
    if ($null -eq $meeting -or $meeting.Rows.Count -ne 1) { throw 'Expected exactly one inserted Meeting row.' }
    if ((Get-RowCount $inserted.Tables['UnknownRow']) -ne 0) { throw 'Create must not transmit unknown rows.' }
    $row = $meeting.Rows[0]
    if ([int]$row['MeetingID', [System.Data.DataRowVersion]::Current] -ne -1) { throw 'Create MeetingID must be native -1.' }
    $currentDate = [datetime]$row['MeetingDate', [System.Data.DataRowVersion]::Current]
    if ($currentDate.Kind -ne [System.DateTimeKind]::Unspecified) { throw 'Create MeetingDate Kind mismatch.' }
    if ($currentDate.Ticks -ne ([datetime]'2026-11-17T10:00:00').Ticks) { throw 'Create MeetingDate mismatch.' }
    $due = [datetime]$row['ResolutionDueDate', [System.Data.DataRowVersion]::Current]
    if ($due.Ticks -ne ([datetime]'2026-11-17T09:00:00').Ticks) { throw 'Create ResolutionDueDate mismatch.' }
    if ([int]$row['MeetingTypeID', [System.Data.DataRowVersion]::Current] -ne 3) { throw 'Create MeetingTypeID mismatch.' }
    if ([int]$row['MeetingLocationID', [System.Data.DataRowVersion]::Current] -ne 4) { throw 'Create MeetingLocationID mismatch.' }
    if ([byte]$row['MeetingStatusID', [System.Data.DataRowVersion]::Current] -ne [byte]10) { throw 'Create MeetingStatusID mismatch.' }
    if ([int]$row['DepartmentID', [System.Data.DataRowVersion]::Current] -ne 2) { throw 'Create DepartmentID mismatch.' }
    if (-not $row.IsNull('TimestampStart')) { throw 'Create must not fabricate TimestampStart.' }
    if ([int]$row['TimestampStartDelta', [System.Data.DataRowVersion]::Current] -ne 0) { throw 'Create TimestampStartDelta default mismatch.' }
    if ($meeting.Columns.Contains('UnknownMeeting')) { throw 'Create schema must not contain UnknownMeeting.' }
    Write-Output 'Validated outbound MinuteTraq Meeting create ds: one inserted Meeting row, native default TimestampStartDelta, no fabricated TimestampStart or unknown rows.'
}

function Validate-UpdateRequest($path) {
    $ds = Read-OutboundDataSet $path
    if (-not $ds.HasChanges()) { throw 'The outbound update ds contains no changes.' }
    $modified = $ds.GetChanges([System.Data.DataRowState]::Modified)
    if ($null -eq $modified) { throw 'The outbound update ds contains no modified rows.' }
    $count = 0
    foreach ($table in $modified.Tables) { $count += $table.Rows.Count }
    if ($count -ne 1) { throw 'Expected exactly one modified row.' }
    $meeting = $modified.Tables['Meeting']
    if ($null -eq $meeting -or $meeting.Rows.Count -ne 1) { throw 'Expected exactly one modified Meeting row.' }
    if ((Get-RowCount $modified.Tables['UnknownRow']) -ne 0) { throw 'Update must not transmit unknown rows.' }
    $row = $meeting.Rows[0]
    if ([int]$row['MeetingID', [System.Data.DataRowVersion]::Original] -ne 501) { throw 'Original MeetingID mismatch.' }
    if ([int]$row['MeetingID', [System.Data.DataRowVersion]::Current] -ne 501) { throw 'Current MeetingID mismatch.' }
    $origDate = [datetime]$row['MeetingDate', [System.Data.DataRowVersion]::Original]
    $currDate = [datetime]$row['MeetingDate', [System.Data.DataRowVersion]::Current]
    if ($origDate.Ticks -ne ([datetime]'2026-11-17T09:00:00').Ticks) { throw 'Original MeetingDate mismatch.' }
    if ($currDate.Ticks -ne ([datetime]'2026-11-17T10:00:00').Ticks) { throw 'Current MeetingDate mismatch.' }
    if ($origDate.Kind -ne [System.DateTimeKind]::Unspecified -or $currDate.Kind -ne [System.DateTimeKind]::Unspecified) { throw 'Update MeetingDate Kind mismatch.' }
    $origDue = [datetime]$row['ResolutionDueDate', [System.Data.DataRowVersion]::Original]
    $currDue = [datetime]$row['ResolutionDueDate', [System.Data.DataRowVersion]::Current]
    if ($origDue.Ticks -ne ([datetime]'2026-11-17T09:00:00').Ticks -or $currDue.Ticks -ne ([datetime]'2026-11-17T09:00:00').Ticks) { throw 'Update ResolutionDueDate mismatch.' }
    if ([int]$row['MeetingTypeID', [System.Data.DataRowVersion]::Current] -ne 3) { throw 'Update MeetingTypeID mismatch.' }
    if ([int]$row['MeetingLocationID', [System.Data.DataRowVersion]::Current] -ne 4) { throw 'Update MeetingLocationID mismatch.' }
    if ([byte]$row['MeetingStatusID', [System.Data.DataRowVersion]::Current] -ne [byte]10) { throw 'Update MeetingStatusID mismatch.' }
    if ([int]$row['DepartmentID', [System.Data.DataRowVersion]::Current] -ne 2) { throw 'Update DepartmentID mismatch.' }
    if ([int]$row['TimestampStartDelta', [System.Data.DataRowVersion]::Current] -ne 0) { throw 'Update TimestampStartDelta mismatch.' }
    if ([string]$row['UnknownMeeting', [System.Data.DataRowVersion]::Original] -ne 'keep-meeting-unknown') { throw 'Original UnknownMeeting mismatch.' }
    if ([string]$row['UnknownMeeting', [System.Data.DataRowVersion]::Current] -ne 'keep-meeting-unknown') { throw 'Current UnknownMeeting mismatch.' }
    $origStart = [datetime]$row['TimestampStart', [System.Data.DataRowVersion]::Original]
    $currStart = [datetime]$row['TimestampStart', [System.Data.DataRowVersion]::Current]
    if ($origStart.Ticks -ne $currStart.Ticks) { throw 'Unchanged TimestampStart must be preserved.' }
    Write-Output 'Validated outbound MinuteTraq Meeting update ds: one modified Meeting row, protected unchanged fields and unknown row excluded from wire changes.'
}

if (-not (Test-Path -LiteralPath $OutDir)) {
    [void](New-Item -ItemType Directory -Path $OutDir)
}
$baselinePath = Join-Path $OutDir 'minutetraq-meeting-baseline-get-response.xml'
$fixtureDataSet = New-MeetingDataSet
Write-BaselineSoapResponse $fixtureDataSet $baselinePath
Write-Output ('Wrote ' + $baselinePath)

if ($ValidateCreate -ne '') {
    Validate-CreateRequest $ValidateCreate
}
if ($ValidateUpdate -ne '') {
    Validate-UpdateRequest $ValidateUpdate
}
