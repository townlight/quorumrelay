import base64

import pytest

from quorumrelay import Source, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.providers import iqm2_soap

URL = 'https://test.iqm2.com/MinuteTraqService/Data_1_0.asmx'
SOURCE = Source('iqm2', URL, input_format=iqm2_soap.FORMAT,
                options={'minutetraq_agency': 'City of Test', 'meeting_id': 501,
                         'document_id': 77, 'document_kind': 'agenda'})
SOURCE_MINUTES = Source('iqm2', URL, input_format=iqm2_soap.FORMAT,
                        options={'minutetraq_agency': 'City of Test', 'meeting_id': 501,
                                 'document_id': 88, 'document_kind': 'minutes'})


def agenda_response(agenda_id=77, meeting_id=501, duplicate_item=False):
    duplicate = ''
    if duplicate_item:
        duplicate = f'''<AgendaItem diffgr:id='AgendaItemDup'><AgendaItemID>9001</AgendaItemID><AgendaID>{agenda_id}</AgendaID><Sort>9</Sort><Title>Duplicate</Title></AgendaItem>'''
    return f'''<?xml version='1.0' encoding='utf-8'?>
<soap:Envelope xmlns:soap='http://schemas.xmlsoap.org/soap/envelope/'>
 <soap:Body>
  <AgendaGetResponse xmlns='{iqm2_soap.SERVICE_NS}'>
   <AgendaGetResult>
    <xs:schema xmlns:xs='http://www.w3.org/2001/XMLSchema' id='DB_1_0'/>
    <diffgr:diffgram xmlns:diffgr='{iqm2_soap.DIFFGR_NS}' xmlns:msdata='urn:schemas-microsoft-com:xml-msdata'>
     <DB_1_0 xmlns='{iqm2_soap.DB_NS}'>
      <Meeting diffgr:id='Meeting1' msdata:rowOrder='0'><MeetingID>{meeting_id}</MeetingID><MeetingDate>2026-11-17T17:30:00</MeetingDate><Updated>rev-7</Updated><UnknownMeeting>keep</UnknownMeeting></Meeting>
      <Agenda diffgr:id='Agenda1'><AgendaID>{agenda_id}</AgendaID><MeetingID>{meeting_id}</MeetingID><FileData>AAECAwQ=</FileData><UnknownAgenda attr='x'>café</UnknownAgenda></Agenda>
      <AgendaItem diffgr:id='AgendaItem1'><AgendaItemID>9001</AgendaItemID><AgendaID>{agenda_id}</AgendaID><ParentItemID xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance' xsi:nil='true'/><Sort>1</Sort><Title>Bridge repair</Title><UnknownChild z='1'>keep</UnknownChild></AgendaItem>
      <AgendaItem diffgr:id='AgendaItem2'><AgendaItemID>9002</AgendaItemID><AgendaID>{agenda_id}</AgendaID><ParentItemID>9001</ParentItemID><Sort>2</Sort><Title>Sidewalk</Title><TitleNil xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance' xsi:nil='true'/><Empty></Empty></AgendaItem>
      <AgendaItem diffgr:id='AgendaItem3' diffgr:hasChanges='deleted'><AgendaItemID>9003</AgendaItemID><AgendaID>{agenda_id}</AgendaID><Sort>3</Sort><Title>Deleted row</Title></AgendaItem>
      <UnknownTable><Row><ID>1</ID><Blob>AAECAwQ=</Blob></Row></UnknownTable>
      {duplicate}
     </DB_1_0>
     <diffgr:before><AgendaItem xmlns='{iqm2_soap.DB_NS}' diffgr:id='AgendaItem1'><AgendaItemID>9001</AgendaItemID><AgendaID>{agenda_id}</AgendaID><Title>Old title</Title></AgendaItem></diffgr:before>
     <diffgr:errors><AgendaItem xmlns='{iqm2_soap.DB_NS}' diffgr:id='AgendaItemErr'><AgendaItemID>9004</AgendaItemID><AgendaID>{agenda_id}</AgendaID><Title>Error row</Title></AgendaItem></diffgr:errors>
    </diffgr:diffgram>
   </AgendaGetResult>
  </AgendaGetResponse>
 </soap:Body>
</soap:Envelope>'''.encode('utf-8')


def minutes_response():
    return f'''<?xml version='1.0' encoding='utf-8'?>
<soap:Envelope xmlns:soap='http://schemas.xmlsoap.org/soap/envelope/'>
 <soap:Body>
  <MinutesGetResponse xmlns='{iqm2_soap.SERVICE_NS}'>
   <MinutesGetResult>
    <xs:schema xmlns:xs='http://www.w3.org/2001/XMLSchema' id='DB_1_0'/>
    <diffgr:diffgram xmlns:diffgr='{iqm2_soap.DIFFGR_NS}'>
     <DB_1_0 xmlns='{iqm2_soap.DB_NS}'>
      <Meeting diffgr:id='Meeting1'><MeetingID>501</MeetingID></Meeting>
      <Minutes diffgr:id='Minutes1'><MinutesID>88</MinutesID><MeetingID>501</MeetingID></Minutes>
      <MinutesItem diffgr:id='MinutesItem1'><MinutesItemID>7001</MinutesItemID><MinutesID>88</MinutesID><ParentItemID xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance' xsi:nil='true'/><Sort>5</Sort><Title>Approved minutes</Title></MinutesItem>
     </DB_1_0>
    </diffgr:diffgram>
   </MinutesGetResult>
  </MinutesGetResponse>
 </soap:Body>
</soap:Envelope>'''.encode('utf-8')


def agenda_response_without_meeting(agenda_id=77, meeting_id=501):
    content = agenda_response(agenda_id=agenda_id, meeting_id=meeting_id).decode('utf-8')
    meeting = f'''<Meeting diffgr:id='Meeting1' msdata:rowOrder='0'><MeetingID>{meeting_id}</MeetingID><MeetingDate>2026-11-17T17:30:00</MeetingDate><Updated>rev-7</Updated><UnknownMeeting>keep</UnknownMeeting></Meeting>'''
    assert meeting in content
    return content.replace(meeting, '', 1).encode('utf-8')


def minutes_response_without_meeting():
    content = minutes_response().decode('utf-8')
    meeting = '''<Meeting diffgr:id='Meeting1'><MeetingID>501</MeetingID></Meeting>'''
    assert meeting in content
    return content.replace(meeting, '', 1).encode('utf-8')


def test_agenda_saved_response_maps_preserves_raw_and_roundtrips(tmp_path):
    engine = create_engine(storage=SQLiteStorage(tmp_path / 'iqm2.sqlite'))
    result = engine.normalize(SOURCE, agenda_response(), input_format=iqm2_soap.FORMAT)
    assert result.status == 'completed', result.public_dict()
    records = result.data['records']
    assert [record['identity']['record_type'] for record in records] == ['meeting', 'agenda', 'agenda_item', 'agenda_item']
    meeting, agenda, item1, item2 = records
    assert meeting['identity']['external_id'] == '501'
    assert meeting['normalized']['meeting_id'] == 501
    assert meeting['normalized']['scheduled_start'] == '2026-11-17T17:30:00'
    assert 'source_updated' not in meeting['normalized']
    updated_field = next(child for child in meeting['original']['children'] if child['tag'] == 'Updated')
    assert updated_field['text'] == 'rev-7'
    assert meeting['identity']['namespace'] == '//test.iqm2.com/MinuteTraqService/agency/City%20of%20Test'
    assert agenda['identity']['external_id'] == '77'
    assert agenda['normalized']['meeting_id'] == 501
    assert item1['identity']['external_id'] == '9001'
    assert item1['normalized']['parent_item_id'] is None
    assert item1['normalized']['sort'] == 1
    assert item1['normalized']['title'] == 'Bridge repair'
    assert item2['identity']['external_id'] == '9002'
    assert item2['normalized']['parent_item_id'] == 9001
    assert item2['normalized']['sort'] == 2
    assert item2['normalized']['title'] == 'Sidewalk'
    assert all(record['identity']['external_id'] != '9003' for record in records)
    parent_field = next(child for child in item1['original']['children'] if child['tag'] == 'ParentItemID')
    assert parent_field['attributes']['{' + iqm2_soap.XSI_NS + '}nil'] == 'true'
    empty_field = next(child for child in item2['original']['children'] if child['tag'] == 'Empty')
    assert empty_field['text'] is None and empty_field['children'] == []
    agenda_file = next(child for child in agenda['original']['children'] if child['tag'] == 'FileData')
    assert agenda_file['text'] == 'AAECAwQ='
    extension = result.data['extensions']['iqm2_soap']
    assert extension['operation'] == 'AgendaGetResponse'
    assert any(row['tag'] == 'UnknownTable' for row in extension['raw_data']['children'])
    assert any(row['tag'] == 'AgendaItem' and row['attributes'].get('{' + iqm2_soap.DIFFGR_NS + '}hasChanges') == 'deleted' for row in extension['raw_data']['children'])
    assert extension['raw_before'] and extension['raw_errors']
    found = engine.execute('search', {'bundle': result.data, 'query': {'terms': ['Bridge repair']}})
    assert len(found.data['hits']) == 1, found.public_dict()
    imported = engine.execute('import_bundle', {'bundle': result.data, 'persist': True})
    assert imported.status == 'completed', imported.public_dict()
    persisted = engine.execute('search', {'query': {'terms': ['Bridge repair']}})
    assert len(persisted.data['hits']) == 1, persisted.public_dict()
    reopened = create_engine(storage=SQLiteStorage(tmp_path / 'iqm2.sqlite'))
    found = reopened.execute('search', {'query': {'terms': ['Bridge repair']}})
    assert len(found.data['hits']) == 1, found.public_dict()
    for format in ('json', 'jsonl', 'zip'):
        exported = engine.execute('export', {'bundle': result.data, 'format': format})
        assert read_bundle(base64.b64decode(exported.data['content_base64']), format=format) == result.data


def test_agenda_saved_response_without_meeting_maps_doc_items_and_roundtrips(tmp_path):
    engine = create_engine(storage=SQLiteStorage(tmp_path / 'iqm2-absent.sqlite'))
    result = engine.normalize(SOURCE, agenda_response_without_meeting(), input_format=iqm2_soap.FORMAT)
    assert result.status == 'completed', result.public_dict()
    records = result.data['records']
    assert [record['identity']['record_type'] for record in records] == ['agenda', 'agenda_item', 'agenda_item']
    agenda, item1, item2 = records
    assert agenda['identity']['external_id'] == '77'
    assert agenda['normalized']['meeting_id'] == 501
    expected_meeting = {'provider': 'iqm2', 'namespace': agenda['identity']['namespace'],
                        'record_type': 'meeting', 'external_id': '501', 'parent': None,
                        'derivation': 'provider_identifier',
                        'stability': 'Provider-issued identifier within the configured namespace.'}
    assert agenda['identity']['parent'] == expected_meeting
    assert {'relation': 'meeting', 'identity': expected_meeting} in agenda['relationships']
    assert item1['identity']['parent'] == agenda['identity']
    assert item2['identity']['parent'] == agenda['identity']
    assert not any(record['identity']['record_type'] == 'meeting' for record in records)
    found = engine.execute('search', {'bundle': result.data, 'query': {'terms': ['Bridge repair']}})
    assert len(found.data['hits']) == 1, found.public_dict()
    imported = engine.execute('import_bundle', {'bundle': result.data, 'persist': True})
    assert imported.status == 'completed', imported.public_dict()
    reopened = create_engine(storage=SQLiteStorage(tmp_path / 'iqm2-absent.sqlite'))
    found = reopened.execute('search', {'query': {'terms': ['Bridge repair']}})
    assert len(found.data['hits']) == 1, found.public_dict()
    for format in ('json', 'jsonl', 'zip'):
        exported = engine.execute('export', {'bundle': result.data, 'format': format})
        assert read_bundle(base64.b64decode(exported.data['content_base64']), format=format) == result.data


def test_minutes_saved_response_maps_minutes_items_and_text():
    result = create_engine().normalize(SOURCE_MINUTES, minutes_response(), input_format=iqm2_soap.FORMAT)
    assert result.status == 'completed', result.public_dict()
    records = result.data['records']
    assert [record['identity']['record_type'] for record in records] == ['meeting', 'minutes', 'minutes_item']
    assert records[1]['identity']['external_id'] == '88'
    assert 'scheduled_start' not in records[0]['normalized']
    assert 'source_updated' not in records[0]['normalized']
    item = records[2]
    assert item['normalized']['document_kind'] == 'minutes'
    assert item['normalized']['sort'] == 5
    assert item['normalized']['title'] == 'Approved minutes'
    assert item['text'][0]['text'] == 'Approved minutes'


def test_minutes_saved_response_without_meeting_maps_doc_item_and_roundtrips():
    result = create_engine().normalize(SOURCE_MINUTES, minutes_response_without_meeting(), input_format=iqm2_soap.FORMAT)
    assert result.status == 'completed', result.public_dict()
    records = result.data['records']
    assert [record['identity']['record_type'] for record in records] == ['minutes', 'minutes_item']
    minutes, item = records
    expected_meeting = {'provider': 'iqm2', 'namespace': minutes['identity']['namespace'],
                        'record_type': 'meeting', 'external_id': '501', 'parent': None,
                        'derivation': 'provider_identifier',
                        'stability': 'Provider-issued identifier within the configured namespace.'}
    assert minutes['identity']['parent'] == expected_meeting
    assert {'relation': 'meeting', 'identity': expected_meeting} in minutes['relationships']
    assert item['identity']['parent'] == minutes['identity']
    assert item['normalized']['title'] == 'Approved minutes'
    assert not any(record['identity']['record_type'] == 'meeting' for record in records)
    found = create_engine().execute('search', {'bundle': result.data, 'query': {'terms': ['Approved minutes']}})
    assert len(found.data['hits']) == 1, found.public_dict()
    for format in ('json', 'jsonl', 'zip'):
        exported = create_engine().execute('export', {'bundle': result.data, 'format': format})
        assert read_bundle(base64.b64decode(exported.data['content_base64']), format=format) == result.data


@pytest.mark.parametrize('content', [
    agenda_response().replace(b'<soap:Envelope', b'<!DOCTYPE foo [<!ENTITY xxe SYSTEM \'file:///etc/passwd\'>]><soap:Envelope', 1),
    b'<?xml version=\'1.0\'?><soap:Envelope xmlns:soap=\'http://schemas.xmlsoap.org/soap/envelope/\'><soap:Body><soap:Fault><faultcode>soap:Server</faultcode></soap:Fault></soap:Body></soap:Envelope>',
    agenda_response().replace(b'</soap:Body>', b'</soap:Body><soap:Body/>'),
    agenda_response().replace(b'</soap:Body>', b'<AgendaGetResponse xmlns=\'http://tempuri.org/MinuteTraqService/Data_1_0\'/></soap:Body>'),
    agenda_response().replace(b'</AgendaGetResult>', b'<diffgr:diffgram xmlns:diffgr=\'urn:schemas-microsoft-com:xml-diffgram-v1\'/></AgendaGetResult>'),
    agenda_response().replace(b'</diffgr:diffgram>', b'<DB_1_0 xmlns=\'http://tempuri.org/DB_1_0.xsd\'/></diffgr:diffgram>'),
    agenda_response().replace(b'</DB_1_0>', b'<Minutes><MinutesID>88</MinutesID><MeetingID>501</MeetingID></Minutes></DB_1_0>'),
    agenda_response(agenda_id=78),
    agenda_response(meeting_id=502),
    agenda_response(duplicate_item=True),
    agenda_response().replace(b'<AgendaID>77</AgendaID><ParentItemID>9001</ParentItemID>', b'<AgendaID>78</AgendaID><ParentItemID>9001</ParentItemID>'),
])
def test_rejects_malformed_foreign_identity_duplicate_and_dtd(content):
    result = create_engine().normalize(SOURCE, content, input_format=iqm2_soap.FORMAT)
    assert result.status == 'failed', result.public_dict()


@pytest.mark.parametrize('old,new', [
    (b'<MeetingID>501</MeetingID>', b"<x:MeetingID xmlns:x='urn:foreign'>501</x:MeetingID>"),
    (b'<ParentItemID>9001</ParentItemID>', b"<x:ParentItemID xmlns:x='urn:foreign'>9001</x:ParentItemID>"),
])
def test_foreign_namespace_consumed_fields_are_rejected(old, new):
    content = agenda_response().replace(old, new, 1)
    result = create_engine().normalize(SOURCE, content, input_format=iqm2_soap.FORMAT)
    assert result.status == 'failed', result.public_dict()


@pytest.mark.parametrize('old,new', [
    (b'<AgendaItemID>9001</AgendaItemID>', b'<AgendaItemID>9223372036854775808</AgendaItemID>'),
    (b'<ParentItemID>9001</ParentItemID>', b'<ParentItemID>9223372036854775808</ParentItemID>'),
    (b'<Sort>1</Sort>', b'<Sort>32768</Sort>'),
])
def test_native_integer_ranges_are_enforced(old, new):
    content = agenda_response().replace(old, new, 1)
    result = create_engine().normalize(SOURCE, content, input_format=iqm2_soap.FORMAT)
    assert result.status == 'failed', result.public_dict()


@pytest.mark.parametrize('old,new', [
    (b"xsi:nil='true'", b"xsi:nil='possibly'"),
    (b"xsi:nil='true'/>", b"xsi:nil='true'>9001</ParentItemID>"),
])
def test_xsi_nil_lexical_and_content_are_rejected(old, new):
    content = agenda_response().replace(old, new, 1)
    result = create_engine().normalize(SOURCE, content, input_format=iqm2_soap.FORMAT)
    assert result.status == 'failed', result.public_dict()


@pytest.mark.parametrize('encoding', ['utf-16-le', 'utf-16-be'])
def test_dtd_rejected_in_utf16_encodings(encoding):
    xml = agenda_response().decode('utf-8')
    xml = xml.replace("<?xml version='1.0' encoding='utf-8'?>",
                      "<?xml version='1.0' encoding='utf-16'?>")
    xml = xml.replace('<soap:Envelope', '<!DOCTYPE foo [<!ENTITY xxe SYSTEM \'file:///etc/passwd\'>]><soap:Envelope', 1)
    result = create_engine().normalize(SOURCE, xml.encode(encoding), input_format=iqm2_soap.FORMAT)
    assert result.status == 'failed', result.public_dict()


def test_parse_bundle_rejects_namespace_mismatch():
    with pytest.raises(ValueError):
        iqm2_soap.parse_bundle(
            SOURCE, '//test.iqm2.com/MinuteTraqService/agency/Wrong', agenda_response())


@pytest.mark.parametrize('options', [
    {'minutetraq_agency': 'City of Test', 'meeting_id': 501, 'document_id': 77},
    {'minutetraq_agency': 'City of Test', 'meeting_id': 501, 'document_id': 77, 'document_kind': 'packet'},
    {'minutetraq_agency': 'City of Test', 'meeting_id': 0, 'document_id': 77, 'document_kind': 'agenda'},
    {'minutetraq_agency': 'City of Test', 'meeting_id': 501, 'document_id': '-1', 'document_kind': 'agenda'},
])
def test_options_are_exact_and_exclude_credentials(options):
    source = Source.from_dict({**SOURCE.public_dict(), 'options': options})
    result = create_engine().normalize(source, agenda_response(), input_format=iqm2_soap.FORMAT)
    assert result.status == 'failed', result.public_dict()


def test_credentials_are_rejected_by_sdk_construction():
    with pytest.raises(ValueError):
        Source.from_dict({**SOURCE.public_dict(), 'options': {
            'minutetraq_agency': 'City of Test', 'meeting_id': 501,
            'document_id': 77, 'document_kind': 'agenda', 'password': 'x'}})


def test_namespace_is_agency_scoped_and_mismatch_rejected():
    validated = create_engine().execute('validate_source', {'source': SOURCE.public_dict()})
    assert validated.status == 'completed', validated.public_dict()
    assert validated.data['source']['namespace'] == '//test.iqm2.com/MinuteTraqService/agency/City%20of%20Test'
    source = Source.from_dict({**SOURCE.public_dict(), 'namespace': '//test.iqm2.com/MinuteTraqService/agency/Wrong'})
    assert create_engine().normalize(source, agenda_response(), input_format=iqm2_soap.FORMAT).status == 'failed'
