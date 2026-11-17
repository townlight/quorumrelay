param(
    [string]$OutDir = (Get-Location).Path,
    [string]$ValidateBigFileAppend = '',
    [string]$ValidateMediaUpdateNew = ''
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Data
Add-Type -AssemblyName System.Xml

function New-BigFileDataSet {
    $ds = New-Object System.Data.DataSet 'DB_1_0'
    $ds.Namespace = 'http://tempuri.org/DB_1_0.xsd'
    $table = New-Object System.Data.DataTable 'BigFile'
    [void]$table.Columns.Add('FileType', [int])
    [void]$table.Columns.Add('ID', [long])
    [void]$table.Columns.Add('FileUpdated', [datetime])
    [void]$table.Columns.Add('FileData', [byte[]])
    [void]$table.Columns.Add('FileSize', [long])
    [void]$table.Columns.Add('FileFormat', [string])
    $table.Columns['FileUpdated'].AllowDBNull = $true
    $table.Columns['FileData'].AllowDBNull = $true
    $table.Columns['FileSize'].AllowDBNull = $true
    $table.Columns['FileFormat'].AllowDBNull = $true
    $table.Columns['FileUpdated'].DateTimeMode = [System.Data.DataSetDateTime]::UnspecifiedLocal
    [void]$ds.Tables.Add($table)
    $ds.AcceptChanges()
    return $ds
}

function New-MediaDataSet {
    $ds = New-Object System.Data.DataSet 'DB_1_0'
    $ds.Namespace = 'http://tempuri.org/DB_1_0.xsd'
    $table = New-Object System.Data.DataTable 'Media'
    [void]$table.Columns.Add('MediaID', [int])
    [void]$table.Columns.Add('MeetingID', [int])
    [void]$table.Columns.Add('MediaEventID', [int])
    [void]$table.Columns.Add('MediaStatusID', [byte])
    [void]$table.Columns.Add('MediaStatusMessage', [string])
    [void]$table.Columns.Add('MediaEncoderID', [short])
    [void]$table.Columns.Add('FileFormat', [string])
    [void]$table.Columns.Add('FileUpdated', [datetime])
    [void]$table.Columns.Add('FileSize', [long])
    [void]$table.Columns.Add('FileData', [byte[]])
    [void]$table.Columns.Add('FileSizeMP4', [long])
    [void]$table.Columns.Add('MediaURL', [string])
    [void]$table.Columns.Add('MediaURLMP4', [string])
    [void]$table.Columns.Add('Started', [datetime])
    [void]$table.Columns.Add('Duration', [int])
    [void]$table.Columns.Add('Published', [datetime])
    [void]$table.Columns.Add('TranscodeStatusID', [byte])
    [void]$table.Columns.Add('TranscodeID', [long])
    [void]$table.Columns.Add('TranscodeFormats', [string])
    [void]$table.Columns.Add('TranscodeTimeLeft', [long])
    [void]$table.Columns.Add('TranscodeProgress', [byte])
    [void]$table.Columns.Add('TranscodeInfo', [string])
    [void]$table.Columns.Add('TranscodeStarted', [datetime])
    [void]$table.Columns.Add('TranscodeUpdated', [datetime])
    [void]$table.Columns.Add('MediaEncoderPresetID', [int])
    [void]$table.Columns.Add('LocalVaultStatusID', [byte])
    [void]$table.Columns.Add('Created', [datetime])
    [void]$table.Columns.Add('CreatedUserID', [int])
    [void]$table.Columns.Add('Updated', [datetime])
    [void]$table.Columns.Add('MediaEncoderStartDelta', [int])
    [void]$table.Columns.Add('UpdatedUserID', [int])
    $table.Columns['MediaID'].AutoIncrement = $true
    $table.Columns['MediaID'].AutoIncrementSeed = -1
    $table.Columns['MediaID'].AutoIncrementStep = -1
    $table.Columns['MediaID'].ReadOnly = $true
    $table.Columns['MediaStatusID'].DefaultValue = [byte]20
    $table.Columns['TranscodeStatusID'].DefaultValue = [byte]10
    $table.Columns['TranscodeProgress'].DefaultValue = [byte]0
    $table.Columns['LocalVaultStatusID'].DefaultValue = [byte]20
    $table.Columns['MediaEncoderStartDelta'].DefaultValue = 0
    foreach ($name in @('FileUpdated', 'Started', 'Published', 'TranscodeStarted', 'TranscodeUpdated', 'Created', 'Updated')) {
        $table.Columns[$name].DateTimeMode = [System.Data.DataSetDateTime]::UnspecifiedLocal
    }
    foreach ($name in @('MediaStatusMessage', 'MediaEncoderID', 'FileFormat', 'FileUpdated', 'FileSize', 'FileData', 'FileSizeMP4', 'MediaURL', 'MediaURLMP4', 'Published', 'TranscodeID', 'TranscodeFormats', 'TranscodeTimeLeft', 'TranscodeInfo', 'TranscodeStarted', 'TranscodeUpdated', 'MediaEncoderPresetID')) {
        $table.Columns[$name].AllowDBNull = $true
    }
    $table.PrimaryKey = @($table.Columns['MediaID'])
    [void]$ds.Tables.Add($table)
    $ds.AcceptChanges()
    return $ds
}

function Get-InlineSchemaElement($dataSet) {
    $sw = New-Object System.IO.StringWriter
    $settings = New-Object System.Xml.XmlWriterSettings
    $settings.OmitXmlDeclaration = $true
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

function Write-SoapResponse($dataSet, $operation, $path) {
    $schema = Get-InlineSchemaElement $dataSet
    $swDiff = New-Object System.IO.StringWriter
    $settingsDiff = New-Object System.Xml.XmlWriterSettings
    $settingsDiff.OmitXmlDeclaration = $true
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
    $writer2.WriteStartElement($operation + 'Response', 'http://tempuri.org/MinuteTraqService/Data_1_0')
    $writer2.WriteStartElement($operation + 'Result', 'http://tempuri.org/MinuteTraqService/Data_1_0')
    $schema.WriteTo($writer2)
    $diffgram.WriteTo($writer2)
    $writer2.WriteEndElement()
    $writer2.WriteEndElement()
    $writer2.WriteEndElement()
    $writer2.WriteEndElement()
    $writer2.WriteEndDocument()
    $writer2.Close()
}

function Read-OutboundDataSet($path) {
    $doc = New-Object System.Xml.XmlDocument
    $doc.Load($path)
    $nodes = $doc.GetElementsByTagName('ds')
    if ($nodes.Count -ne 1) { throw 'Expected exactly one ds element.' }
    $dsNode = $nodes[0]
    $sw = New-Object System.IO.StringWriter
    $writer = [System.Xml.XmlWriter]::Create($sw)
    $dsNode.WriteTo($writer)
    $writer.Close()
    $doc2 = New-Object System.Xml.XmlDocument
    $doc2.PreserveWhitespace = $true
    $doc2.LoadXml($sw.ToString())
    $schemaNode = $null
    $diffgramNode = $null
    foreach ($child in $doc2.DocumentElement.ChildNodes) {
        if ($child.NodeType -ne 'Element') { continue }
        if ($child.LocalName -eq 'schema' -and $child.NamespaceURI -eq 'http://www.w3.org/2001/XMLSchema') { $schemaNode = $child }
        elseif ($child.LocalName -eq 'diffgram' -and $child.NamespaceURI -eq 'urn:schemas-microsoft-com:xml-diffgram-v1') { $diffgramNode = $child }
    }
    if ($null -eq $schemaNode -or $null -eq $diffgramNode) { throw 'Outbound ds must contain schema and diffgram.' }
    $ds = New-Object System.Data.DataSet
    $swSchema = New-Object System.IO.StringWriter
    $writerSchema = [System.Xml.XmlWriter]::Create($swSchema)
    $schemaNode.WriteTo($writerSchema)
    $writerSchema.Close()
    $readerSchema = New-Object System.IO.StringReader($swSchema.ToString())
    $xmlReaderSchema = [System.Xml.XmlReader]::Create($readerSchema)
    try { $ds.ReadXmlSchema($xmlReaderSchema) } finally { $xmlReaderSchema.Close() }
    $ds.EnforceConstraints = $false
    $swDiff = New-Object System.IO.StringWriter
    $writerDiff = [System.Xml.XmlWriter]::Create($swDiff)
    $diffgramNode.WriteTo($writerDiff)
    $writerDiff.Close()
    $readerDiff = New-Object System.IO.StringReader($swDiff.ToString())
    $xmlReaderDiff = [System.Xml.XmlReader]::Create($readerDiff)
    try { [void]$ds.ReadXml($xmlReaderDiff, [System.Data.XmlReadMode]::DiffGram) } finally { $xmlReaderDiff.Close() }
    return $ds
}

function Validate-BigFileAppend($path) {
    $ds = Read-OutboundDataSet $path
    if (-not $ds.HasChanges()) { throw 'BigFileAppend must contain a change.' }
    $modified = $ds.GetChanges([System.Data.DataRowState]::Modified)
    if ($null -eq $modified) { throw 'BigFileAppend must contain a modified BigFile row.' }
    $table = $modified.Tables['BigFile']
    if ($null -eq $table -or $table.Rows.Count -ne 1) { throw 'Expected exactly one modified BigFile row.' }
    $row = $table.Rows[0]
    if ([int]($row['FileType', [System.Data.DataRowVersion]::Current]) -ne 11) { throw 'FileType must be 11.' }
    if ([long]($row['ID', [System.Data.DataRowVersion]::Current]) -ne -1) { throw 'New-row BigFile ID must remain -1.' }
    if ($row.IsNull('FileData')) { throw 'FileData chunk is required.' }
    $bytes = [byte[]]($row['FileData', [System.Data.DataRowVersion]::Current])
    if ($bytes.Length -ne 512000) { throw 'Expected one 512000-byte chunk.' }
    if (-not $row.IsNull('FileSize')) { throw 'FileSize offset must not be fabricated locally.' }
    if (-not $row.IsNull('FileUpdated')) { throw 'FileUpdated must not be fabricated locally.' }
    Write-Output 'Validated actual BigFileAppend request: native FileType=11, temporary ID=-1, one 512000-byte FileData chunk, no local offset/timestamp fabrication.'
}

function Validate-MediaUpdateNew($path) {
    $ds = Read-OutboundDataSet $path
    if (-not $ds.HasChanges()) { throw 'MediaUpdate must contain a change.' }
    $inserted = $ds.GetChanges([System.Data.DataRowState]::Added)
    if ($null -eq $inserted) { throw 'New-row MediaUpdate must contain an inserted Media row.' }
    $table = $inserted.Tables['Media']
    if ($null -eq $table -or $table.Rows.Count -ne 1) { throw 'Expected exactly one inserted Media row.' }
    $row = $table.Rows[0]
    if ([int]($row['MediaID', [System.Data.DataRowVersion]::Current]) -ne -1) { throw 'MediaID must remain native -1 through upload.' }
    if ([int]($row['MeetingID', [System.Data.DataRowVersion]::Current]) -ne 7001) { throw 'MeetingID mismatch.' }
    if ([int]($row['Duration', [System.Data.DataRowVersion]::Current]) -ne 0) { throw 'Duration must be 0.' }
    if ([byte]($row['MediaStatusID', [System.Data.DataRowVersion]::Current]) -ne [byte]100) { throw 'MediaStatusID must be 100.' }
    if ([string]($row['FileFormat', [System.Data.DataRowVersion]::Current]) -ne 'mp4') { throw 'FileFormat mismatch.' }
    if ([long]($row['FileSize', [System.Data.DataRowVersion]::Current]) -ne 1000) { throw 'FileSize mismatch.' }
    $fileData = [byte[]]($row['FileData', [System.Data.DataRowVersion]::Current])
    $marker = [System.Text.Encoding]::ASCII.GetString($fileData)
    if ($marker -ne '~~BIGFILE~~recording.mp4') { throw 'FileData marker must contain only the selected basename.' }
    if (-not $row.IsNull('Created') -or -not $row.IsNull('CreatedUserID') -or -not $row.IsNull('Updated') -or -not $row.IsNull('UpdatedUserID')) {
        throw 'Audit columns must remain unset on the client new row.'
    }
    Write-Output 'Validated actual MediaUpdate new-row request: native -1 MediaID, explicit MeetingID, Duration=0, MediaStatusID=100, bounded BIGFILE marker, FileSize, and unset audit columns.'
}

if (-not (Test-Path -LiteralPath $OutDir)) { [void](New-Item -ItemType Directory -Path $OutDir) }
$big = New-BigFileDataSet
$big.Tables['BigFile'].Rows.Add(11, [long]-1, $null, $null, $null, $null) | Out-Null
$big.AcceptChanges()
$bigPath = Join-Path $OutDir 'minutetraq-media-bigfile-upload-info.xml'
Write-SoapResponse $big 'BigFileGetUploadInfo' $bigPath
Write-Output ('Wrote ' + $bigPath)
if ($ValidateBigFileAppend -ne '') { Validate-BigFileAppend $ValidateBigFileAppend }
if ($ValidateMediaUpdateNew -ne '') { Validate-MediaUpdateNew $ValidateMediaUpdateNew }
