param(
    [string]$OutDir = (Get-Location).Path,
    [string]$ValidateRequest = ''
)

$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Data
Add-Type -AssemblyName System.Xml

function New-MinuteTraqDataSet {
    $ds = New-Object System.Data.DataSet 'DB_1_0'
    $ds.Namespace = 'http://tempuri.org/DB_1_0.xsd'

    $meeting = New-Object System.Data.DataTable 'Meeting'
    [void]$meeting.Columns.Add('MeetingID', [int])
    [void]$meeting.Columns.Add('MeetingDate', [datetime])
    [void]$meeting.Columns.Add('UnknownMeeting', [string])
    $meeting.PrimaryKey = @($meeting.Columns['MeetingID'])
    [void]$ds.Tables.Add($meeting)

    $agenda = New-Object System.Data.DataTable 'Agenda'
    [void]$agenda.Columns.Add('AgendaID', [int])
    [void]$agenda.Columns.Add('MeetingID', [int])
    [void]$agenda.Columns.Add('Updated', [datetime])
    [void]$agenda.Columns.Add('UnknownParent', [string])
    $agenda.PrimaryKey = @($agenda.Columns['AgendaID'])
    [void]$ds.Tables.Add($agenda)

    $item = New-Object System.Data.DataTable 'AgendaItem'
    [void]$item.Columns.Add('AgendaItemID', [long])
    [void]$item.Columns.Add('AgendaID', [int])
    [void]$item.Columns.Add('Sort', [System.Int16])
    [void]$item.Columns.Add('Title', [string])
    [void]$item.Columns.Add('UnknownItem', [string])
    $item.PrimaryKey = @($item.Columns['AgendaItemID'])
    [void]$ds.Tables.Add($item)

    [void]$ds.Relations.Add('Meeting_Agenda', $meeting.Columns['MeetingID'], $agenda.Columns['MeetingID'])
    [void]$ds.Relations.Add('Agenda_AgendaItem', $agenda.Columns['AgendaID'], $item.Columns['AgendaID'])

    $meetingDate = [datetime]'2026-11-17T09:00:00'
    $baselineUpdated = [datetime]'2026-11-17T17:00:00'
    [void]$meeting.Rows.Add(501, $meetingDate, 'keep-meeting')
    [void]$agenda.Rows.Add(77, 501, $baselineUpdated, 'keep-parent')
    [void]$item.Rows.Add(9001, 77, 1, 'Bridge repair', 'keep-item')
    [void]$item.Rows.Add(9002, 77, 2, ' ', 'keep-whitespace')
    [void]$item.Rows.Add(9003, 77, 3, [DBNull]::Value, 'keep-null')
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
        if ($child.NodeType -eq 'Element' -and $child.LocalName -eq 'schema' -and
            $child.NamespaceURI -eq 'http://www.w3.org/2001/XMLSchema') {
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
    $writer2.WriteStartElement('AgendaGetResponse', 'http://tempuri.org/MinuteTraqService/Data_1_0')
    $writer2.WriteStartElement('AgendaGetResult', 'http://tempuri.org/MinuteTraqService/Data_1_0')
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

function Validate-OutboundRequest($path) {
    $dsNode = Get-SoapDataSetNode $path
    $sw = New-Object System.IO.StringWriter
    $writer = [System.Xml.XmlWriter]::Create($sw)
    $dsNode.WriteTo($writer)
    $writer.Close()
    $dsText = $sw.ToString()

    $doc = New-Object System.Xml.XmlDocument
    $doc.PreserveWhitespace = $true
    $doc.LoadXml($dsText)
    $schemaNode = $null
    $diffgramNode = $null
    foreach ($child in $doc.DocumentElement.ChildNodes) {
        if ($child.NodeType -ne 'Element') { continue }
        if ($child.LocalName -eq 'schema' -and
            $child.NamespaceURI -eq 'http://www.w3.org/2001/XMLSchema') {
            $schemaNode = $child
        }
        elseif ($child.LocalName -eq 'diffgram' -and
                $child.NamespaceURI -eq 'urn:schemas-microsoft-com:xml-diffgram-v1') {
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
        $ds.ReadXml($xmlReaderDiff, [System.Data.XmlReadMode]::DiffGram)
    }
    finally {
        $xmlReaderDiff.Close()
    }

    if (-not $ds.HasChanges()) { throw 'The outbound ds contains no changes.' }
    $modified = $ds.GetChanges([System.Data.DataRowState]::Modified)
    if ($null -eq $modified) { throw 'The outbound ds contains no modified rows.' }
    $modifiedCount = 0
    foreach ($table in $modified.Tables) { $modifiedCount += $table.Rows.Count }
    if ($modifiedCount -ne 2) { throw 'Expected exactly two modified rows.' }

    $agenda = $modified.Tables['Agenda']
    $item = $modified.Tables['AgendaItem']
    if ($null -eq $agenda -or $agenda.Rows.Count -ne 1) {
        throw 'Expected exactly one modified Agenda row.'
    }
    if ($null -eq $item -or $item.Rows.Count -ne 1) {
        throw 'Expected exactly one modified AgendaItem row.'
    }

    if ([int]$agenda.Rows[0]['AgendaID', [System.Data.DataRowVersion]::Original] -ne 77) { throw 'Original AgendaID mismatch.' }
    if ([int]$agenda.Rows[0]['AgendaID', [System.Data.DataRowVersion]::Current] -ne 77) { throw 'Current AgendaID mismatch.' }
    if ([int]$agenda.Rows[0]['MeetingID', [System.Data.DataRowVersion]::Original] -ne 501) { throw 'Original MeetingID mismatch.' }
    if ([int]$agenda.Rows[0]['MeetingID', [System.Data.DataRowVersion]::Current] -ne 501) { throw 'Current MeetingID mismatch.' }
    if ([long]$item.Rows[0]['AgendaItemID', [System.Data.DataRowVersion]::Original] -ne 9001) { throw 'Original AgendaItemID mismatch.' }
    if ([long]$item.Rows[0]['AgendaItemID', [System.Data.DataRowVersion]::Current] -ne 9001) { throw 'Current AgendaItemID mismatch.' }
    if ([int]$item.Rows[0]['AgendaID', [System.Data.DataRowVersion]::Original] -ne 77) { throw 'Original item AgendaID mismatch.' }
    if ([int]$item.Rows[0]['AgendaID', [System.Data.DataRowVersion]::Current] -ne 77) { throw 'Current item AgendaID mismatch.' }

    $updatedOriginal = [datetime]$agenda.Rows[0]['Updated', [System.Data.DataRowVersion]::Original]
    $updatedCurrent = [datetime]$agenda.Rows[0]['Updated', [System.Data.DataRowVersion]::Current]
    $expectedOriginal = [datetime]'2026-11-17T17:00:00'
    $expectedCurrent = [datetime]'2026-11-17T18:00:00'
    if ($updatedOriginal.Kind -ne [System.DateTimeKind]::Unspecified) { throw 'Original Updated Kind mismatch.' }
    if ($updatedCurrent.Kind -ne [System.DateTimeKind]::Unspecified) { throw 'Current Updated Kind mismatch.' }
    if ($updatedOriginal.Ticks -ne $expectedOriginal.Ticks) { throw 'Original Updated value mismatch.' }
    if ($updatedCurrent.Ticks -ne $expectedCurrent.Ticks) { throw 'Current Updated value mismatch.' }

    $titleOriginal = $item.Rows[0]['Title', [System.Data.DataRowVersion]::Original]
    $titleCurrent = $item.Rows[0]['Title', [System.Data.DataRowVersion]::Current]
    if ([string]$titleOriginal -ne 'Bridge repair') { throw 'Original Title value mismatch.' }
    if ([string]$titleCurrent -ne 'New bridge') { throw 'Current Title value mismatch.' }

    if ([string]$agenda.Rows[0]['UnknownParent', [System.Data.DataRowVersion]::Original] -ne 'keep-parent') { throw 'Original UnknownParent mismatch.' }
    if ([string]$agenda.Rows[0]['UnknownParent', [System.Data.DataRowVersion]::Current] -ne 'keep-parent') { throw 'Current UnknownParent mismatch.' }
    if ([string]$item.Rows[0]['UnknownItem', [System.Data.DataRowVersion]::Original] -ne 'keep-item') { throw 'Original UnknownItem mismatch.' }
    if ([string]$item.Rows[0]['UnknownItem', [System.Data.DataRowVersion]::Current] -ne 'keep-item') { throw 'Current UnknownItem mismatch.' }

    Write-Output 'Validated outbound MinuteTraq ds: exactly two modified rows, IDs, wall-clock Updated values, titles and unknown fields match.'
}

if (-not (Test-Path -LiteralPath $OutDir)) {
    [void](New-Item -ItemType Directory -Path $OutDir)
}
$baselinePath = Join-Path $OutDir 'minutetraq-baseline-get-response.xml'
$fixtureDataSet = New-MinuteTraqDataSet
Write-BaselineSoapResponse $fixtureDataSet $baselinePath
Write-Output ('Wrote ' + $baselinePath)

if ($ValidateRequest -ne '') {
    Validate-OutboundRequest $ValidateRequest
}
