'''Boardable native meeting supporting-document upload through WriteCoordinator.'''

from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import re
from time import monotonic
from urllib.parse import quote, unquote, urlsplit

from ..engine import canonical_hash
from ..write_adapters import AmbiguousWrite, WriteCancelled, WriteChange, WriteFailure
from ..write_transport import WriteResponse
from .boardable_builder_write import BoardableBuilderWriteAdapter, _safe_filename, _safe_mime
from .boardable_meeting_write import (
    BoardableMeetingWriteAdapter, _SLUG_RE, _canonical, _check_json_bounds,
    _check_prepared_size, _falseish, _native_id, _normalize_meeting, _scrub,
)

_ATTACHABLE_TYPE = 'App' + chr(92) + 'Boardable' + chr(92) + 'Meetings' + chr(92) + 'Meeting'
_UUIDABLE_TYPE = 'App' + chr(92) + 'Boardable' + chr(92) + 'Attachments' + chr(92) + 'Attachment'
_SAFE_ID_RE = re.compile(r'[1-9][0-9]{0,18}')
_DOWNLOAD_SEGMENT = 'attachments/uploads/download/'
_DOCUMENT_SEGMENT = 'documents/'
_ATTACHMENT_VOLATILE = {
    'created_at', 'updated_at', 'pdf', 'iconUrl', 'bareIconUrl', 'thumbUrl', 'thumbnail',
}
_UUID_VOLATILE = {'created_at', 'updated_at'}


def _download_url(row):
    value = row.get('downloadUrl')
    if value is None:
        value = row.get('url')
    return value


def _expected_download(source_url, identity, filename):
    return source_url + _DOWNLOAD_SEGMENT + str(identity) + '/' + quote(filename, safe='')


def _safe_path_segments(path):
    if not isinstance(path, str) or not path.startswith('/'):
        return None
    result = []
    for item in path.split('/'):
        decoded = unquote(item)
        if decoded in {'.', '..'} or '/' in decoded or chr(92) in decoded:
            return None
        result.append(decoded)
    return result


def _same_url(value, expected):
    if not isinstance(value, str) or not isinstance(expected, str):
        return False
    try:
        left = urlsplit(value)
        right = urlsplit(expected)
        left_port = left.port
        right_port = right.port
    except ValueError:
        return False
    if (left.scheme != 'https' or left.netloc != 'app.boardable.com' or left.username
            or left.password or left_port is not None or left.query or left.fragment):
        return False
    if (right.scheme != 'https' or right.netloc != 'app.boardable.com' or right.username
            or right.password or right_port is not None or right.query or right.fragment):
        return False
    left_path = _safe_path_segments(left.path)
    right_path = _safe_path_segments(right.path)
    return left_path is not None and left_path == right_path


def _uuid_slug(row):
    identity = _native_id(row.get('id'))
    uuid_value = row.get('uuid')
    if not isinstance(uuid_value, dict):
        raise ValueError('The attachment UUID identity is missing.')
    if _native_id(uuid_value.get('uuidable_id')) != identity:
        raise ValueError('The attachment UUID points at another native ID.')
    if uuid_value.get('uuidable_type') != _UUIDABLE_TYPE:
        raise ValueError('The attachment UUID type is not the exact native attachment type.')
    slug = uuid_value.get('short_slug')
    if not isinstance(slug, str) or _SLUG_RE.fullmatch(slug) is None:
        raise ValueError('The attachment short slug is unsafe or missing.')
    return slug


def _clean_row(row):
    result = _scrub(deepcopy(row))
    for key in _ATTACHMENT_VOLATILE:
        result.pop(key, None)
    uuid_value = result.get('uuid')
    if isinstance(uuid_value, dict):
        result['uuid'] = {key: value for key, value in uuid_value.items() if key not in _UUID_VOLATILE}
    return result


class BoardableMeetingDocumentsWriteAdapter(BoardableMeetingWriteAdapter):
    _validate_part = BoardableBuilderWriteAdapter._validate_part
    _read_part = BoardableBuilderWriteAdapter._read_part
    _multipart_body = BoardableBuilderWriteAdapter._multipart_body

    def __init__(self, transport=None):
        super().__init__(transport)

    def credentials(self, source, context):
        config = context.credentials.get(self.provider)
        if not isinstance(config, dict) or config.get('current_meeting_documents') is not True:
            raise WriteFailure('permission_denied', 'The explicit Boardable meeting document credential is required.')
        if config.get('current_meeting_form') is not True:
            raise WriteFailure('permission_denied', 'The Boardable document mode requires current_meeting_form.')
        if any(config.get(flag) is True for flag in ('current_meeting_series', 'legacy_agenda_editor', 'current_agenda_builder')):
            raise WriteFailure('permission_denied', 'The Boardable document mode is mutually exclusive with series, legacy and agenda builder modes.')
        base = super().credentials(source, context)
        try:
            _native_id(base.get('organization_id'))
            _native_id(base.get('owner_id'))
        except ValueError:
            raise WriteFailure('permission_denied', 'Exact native organization and owner IDs are required.') from None
        permissions = base.get('permissions')
        if not isinstance(permissions, (list, tuple, set, frozenset)) or 'meeting_document:upload' not in permissions:
            raise WriteFailure('permission_denied', 'The meeting_document:upload permission is required.')
        ids = base.get('meeting_ids')
        if not isinstance(ids, (list, tuple, set, frozenset)) or not ids:
            raise WriteFailure('permission_denied', 'An explicit Boardable meeting allowlist is required.')
        for value in ids:
            if type(value) is int:
                if not 0 < value < 10 ** 19:
                    raise WriteFailure('permission_denied', 'The Boardable meeting allowlist is malformed.')
            elif not isinstance(value, str) or _SAFE_ID_RE.fullmatch(value) is None:
                raise WriteFailure('permission_denied', 'The Boardable meeting allowlist is malformed.')
        urls = base.get('meeting_urls')
        if not isinstance(urls, dict) or not urls:
            raise WriteFailure('permission_denied', 'Exact trusted meeting URLs are required.')
        for key, value in urls.items():
            if not isinstance(key, str) or _SAFE_ID_RE.fullmatch(key) is None or not isinstance(value, str):
                raise WriteFailure('permission_denied', 'The trusted Boardable meeting URL map is malformed.')
            try:
                canonical, _ = _canonical(source.url, value)
            except ValueError:
                raise WriteFailure('permission_denied', 'The trusted Boardable meeting URL is not canonical.') from None
            if canonical != value:
                raise WriteFailure('permission_denied', 'The trusted Boardable meeting URL is not canonical.')
        return base

    def validate_source(self, source, context):
        if source.provider != self.provider or not source.namespace:
            raise ValueError('A Boardable document source requires the exact provider and namespace.')
        self.credentials(source, context)

    def _meeting_id(self, change):
        value = change.meeting_id
        if not isinstance(value, str) or _SAFE_ID_RE.fullmatch(value) is None:
            raise ValueError('A bounded positive ASCII meeting_id string is required.')
        return value

    def _meeting_url(self, source, config, meeting_id):
        ids = config.get('meeting_ids')
        if not isinstance(ids, (list, tuple, set, frozenset)) or not any(
                (str(value) == meeting_id) for value in ids if not isinstance(value, bool) and isinstance(value, (str, int))):
            raise WriteFailure('permission_denied', 'The meeting is outside the trusted Boardable allowlist.')
        urls = config.get('meeting_urls')
        value = urls.get(meeting_id) if isinstance(urls, dict) else None
        if not isinstance(value, str):
            raise WriteFailure('permission_denied', 'The meeting URL is outside the trusted Boardable policy.')
        try:
            canonical, _ = _canonical(source.url, value)
        except ValueError:
            raise WriteFailure('permission_denied', 'The trusted Boardable meeting URL is invalid.') from None
        if canonical != value:
            raise WriteFailure('permission_denied', 'The trusted Boardable meeting URL is not canonical.')
        return value

    def authorize(self, source, change, context):
        config = self.credentials(source, context)
        if (change.entity != 'meeting_document' or change.operation != 'upload'
                or change.resource_id is not None or change.parent_id is not None
                or change.language is not None or change.page_number is not None):
            raise WriteFailure('mapping_unverified', 'Only one root meeting-document upload is mapped.')
        if not isinstance(change.fields, dict) or change.fields != {}:
            raise ValueError('Meeting-document uploads require empty fields.')
        if not isinstance(change.key, str) or not 0 < len(change.key) <= 200:
            raise ValueError('A bounded change key is required.')
        meeting_id = self._meeting_id(change)
        self._meeting_url(source, config, meeting_id)
        if len(change.files) != 1:
            raise ValueError('Exactly one immutable bound file is required.')
        self._validate_part(change.files[0])
        return config

    def _headers(self, config, content_type=None):
        headers = {
            'Accept': 'application/json',
            'Cookie': config['session_cookie'],
            'X-Requested-With': 'XMLHttpRequest',
            'X-XSRF-TOKEN': config['xsrf_token'],
        }
        if content_type is not None:
            headers['Content-Type'] = content_type
        return headers

    def _request_json(self, source, change, context, method, url, body, bounds, deadline,
                      *, content_type=None, expected_status=200, post_send=False, allow_cancelled=False):
        self.authorize(source, change, context)
        if not allow_cancelled and context.check_cancelled():
            raise WriteCancelled()
        config = self.credentials(source, context)
        headers = self._headers(config, content_type)
        encoded = None
        limit = min(bounds.parser_bytes, bounds.transfer_bytes)
        if body is not None:
            encoded = json.dumps(body, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
            if len(encoded) > limit:
                raise ValueError('The Boardable document read request exceeds byte bounds.')
        remaining = deadline - monotonic()
        if remaining <= 0:
            if post_send:
                raise AmbiguousWrite('The Boardable document read deadline expired after send.')
            raise WriteFailure('deadline_exceeded', 'The Boardable operation deadline expired.')
        try:
            response = self.transport.send(url, method=method, body=encoded, headers=headers,
                                           byte_limit=limit, deadline_seconds=remaining)
        except (OSError, TimeoutError, RuntimeError, ValueError):
            if post_send:
                raise AmbiguousWrite('The Boardable document read could not be confirmed.') from None
            raise WriteFailure('provider_rejected', 'The Boardable document read could not be completed.') from None
        if not isinstance(response, WriteResponse) or len(response.content) > limit:
            if post_send:
                raise AmbiguousWrite('Invalid or oversized Boardable document read response.')
            raise WriteFailure('provider_rejected', 'Invalid or oversized Boardable document read response.')
        if response.status in {401, 403}:
            if post_send:
                raise AmbiguousWrite('Boardable denied the post-send document read.')
            raise WriteFailure('permission_denied', 'Boardable denied the operation.')
        if response.status in {409, 412}:
            if post_send:
                raise AmbiguousWrite('Boardable returned a post-send conflict read response.')
            raise WriteFailure('conflict', 'Boardable rejected a conflicting change.')
        if not 200 <= response.status < 300:
            if post_send:
                raise AmbiguousWrite('Boardable did not return a confirmed document read response.')
            raise WriteFailure('provider_rejected', 'Boardable rejected the document read request.')
        if response.status != expected_status:
            if post_send:
                raise AmbiguousWrite('Boardable returned an unexpected post-send document read status.')
            raise WriteFailure('provider_rejected', 'Boardable returned an unexpected document read status.')
        try:
            return json.loads(response.content)
        except (UnicodeError, ValueError):
            if post_send:
                raise AmbiguousWrite('Boardable returned invalid post-send document JSON.') from None
            raise WriteFailure('provider_rejected', 'Boardable returned invalid document JSON.') from None

    def _send_upload(self, source, change, context, bounds, deadline, body, content_type):
        self.authorize(source, change, context)
        if context.check_cancelled():
            raise WriteCancelled()
        config = self.credentials(source, context)
        if len(body) > bounds.transfer_bytes:
            raise ValueError('The Boardable multipart document request exceeds transfer bounds.')
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise WriteFailure('deadline_exceeded', 'The Boardable document upload deadline expired.')
        headers = self._headers(config, content_type)
        try:
            response = self.transport.send(source.url + 'attachments/upload', method='POST', body=body,
                                           headers=headers, byte_limit=bounds.transfer_bytes,
                                           deadline_seconds=remaining)
        except (OSError, TimeoutError, RuntimeError, ValueError):
            raise AmbiguousWrite() from None
        if not isinstance(response, WriteResponse) or len(response.content) > bounds.transfer_bytes:
            raise AmbiguousWrite('The Boardable document upload response is invalid or oversized.')
        if response.status != 200 or response.content != b'':
            raise AmbiguousWrite('The Boardable document upload did not return the observed empty success response.')

    def _normalize_attachment(self, row, meeting_id, config, source_url):
        if not isinstance(row, dict):
            raise WriteFailure('provider_rejected', 'A canonical attachment row is not an object.')
        identity = _native_id(row.get('id'))
        if _native_id(row.get('attachable_id')) != int(meeting_id):
            raise WriteFailure('permission_denied', 'A canonical attachment belongs to another meeting.')
        if row.get('attachable_type') != _ATTACHABLE_TYPE:
            raise WriteFailure('permission_denied', 'A canonical attachment has the wrong native attachable type.')
        if _native_id(row.get('organization_id')) != _native_id(config.get('organization_id')):
            raise WriteFailure('permission_denied', 'A canonical attachment belongs to another organization.')
        _native_id(row.get('owner_id'))
        folder_id = row.get('folder_id')
        if type(folder_id) is not int or not 0 <= folder_id < 10 ** 19:
            raise WriteFailure('provider_rejected', 'A canonical attachment folder_id is malformed.')
        filename = _safe_filename(row.get('filename'))
        _safe_mime(row.get('mime_type'))
        size = row.get('file_size')
        if type(size) is not int or size < 0:
            raise WriteFailure('provider_rejected', 'A canonical attachment file_size is malformed.')
        download = _download_url(row)
        if download is not None and not _same_url(download, _expected_download(source_url, identity, filename)):
            raise WriteFailure('permission_denied', 'A canonical attachment download URL is outside the exact route.')
        if 'uuid' in row:
            _uuid_slug(row)
        result = _clean_row(row)
        result['id'] = identity
        result['attachable_id'] = int(meeting_id)
        result['attachable_type'] = _ATTACHABLE_TYPE
        result['organization_id'] = _native_id(config.get('organization_id'))
        result['owner_id'] = _native_id(row.get('owner_id'))
        result['folder_id'] = folder_id
        result['filename'] = filename
        result['mime_type'] = _safe_mime(row.get('mime_type'))
        result['file_size'] = size
        return result

    def _normalize_attachments(self, rows, meeting_id, config, source_url, bounds):
        if not isinstance(rows, list) or len(rows) > bounds.max_records:
            raise WriteFailure('provider_rejected', 'The canonical attachment list is missing or oversized.')
        result, seen = [], set()
        for row in rows:
            value = self._normalize_attachment(row, meeting_id, config, source_url)
            if value['id'] in seen:
                raise WriteFailure('provider_rejected', 'The canonical attachment list repeats a native ID.')
            seen.add(value['id'])
            result.append(value)
        return result

    def _normalize_root_list(self, raw, source_url, bounds):
        if not isinstance(raw, dict):
            raise WriteFailure('provider_rejected', 'The root attachment list response is incomplete.')
        required = {'items', 'folders', 'current_folder', 'breadcrumbs'}
        if not required.issubset(raw) or not isinstance(raw['items'], list) or not isinstance(raw['folders'], list):
            raise WriteFailure('provider_rejected', 'The root attachment list response is incomplete.')
        if len(raw['items']) > bounds.max_records or len(raw['folders']) > bounds.max_records:
            raise WriteFailure('provider_rejected', 'The root attachment list exceeds record bounds.')
        if raw['current_folder'] is not None:
            raise WriteFailure('permission_denied', 'The root attachment list is not rooted at the root folder.')
        breadcrumbs = raw['breadcrumbs']
        if (not isinstance(breadcrumbs, list) or len(breadcrumbs) != 1
                or not isinstance(breadcrumbs[0], dict)
                or set(breadcrumbs[0]) - {'label', 'slug'}
                or breadcrumbs[0].get('label') != 'All files'
                or breadcrumbs[0].get('slug') != ''):
            raise WriteFailure('provider_rejected', 'The root attachment breadcrumbs are not the captured root shape.')
        items, seen = [], set()
        for row in raw['items']:
            if not isinstance(row, dict):
                raise WriteFailure('provider_rejected', 'A root attachment item is not an object.')
            identity = _native_id(row.get('id'))
            if identity in seen:
                raise WriteFailure('provider_rejected', 'The root attachment list repeats a native ID.')
            seen.add(identity)
            filename = _safe_filename(row.get('filename'))
            size = row.get('file_size')
            if type(size) is not int or size < 0:
                raise WriteFailure('provider_rejected', 'A root attachment file_size is malformed.')
            download = _download_url(row)
            if not _same_url(download, _expected_download(source_url, identity, filename)):
                raise WriteFailure('permission_denied', 'A root attachment download URL is outside the exact route.')
            _uuid_slug(row)
            value = _clean_row(row)
            value['id'] = identity
            value['filename'] = filename
            value['file_size'] = size
            value['downloadUrl'] = download
            items.append(value)
        folders = []
        folder_ids = set()
        for folder in raw['folders']:
            if not isinstance(folder, dict):
                raise WriteFailure('provider_rejected', 'A root folder row is not an object.')
            identity = _native_id(folder.get('id'))
            if identity in folder_ids:
                raise WriteFailure('provider_rejected', 'The root folder list repeats a native ID.')
            folder_ids.add(identity)
            value = _scrub(deepcopy(folder))
            value['id'] = identity
            folders.append(value)
        result = _scrub(deepcopy(raw))
        result['items'] = items
        result['folders'] = folders
        result['current_folder'] = None
        result['breadcrumbs'] = [{'label': 'All files', 'slug': ''}]
        return result

    def _validate_meeting_state(self, norm, resource, config):
        owner_id = _native_id(config.get('owner_id'))
        if _native_id(norm.get('owner_id')) != owner_id:
            raise WriteFailure('permission_denied', 'The meeting is not owned by the trusted document owner.')
        if resource.get('owner_id') is not None and _native_id(resource.get('owner_id')) != owner_id:
            raise WriteFailure('permission_denied', 'The meeting resource owner differs from policy.')
        for key in ('public_member_dashboard', 'public_page', 'published', 'minutes_published',
                    'published_level', 'materials_published_status', 'published_materials_status'):
            if not _falseish(norm.get(key)):
                raise WriteFailure('permission_denied', 'The meeting is not private and unpublished.')
        if norm.get('published_at') is not None:
            raise WriteFailure('permission_denied', 'The meeting is not private and unpublished.')
        if resource.get('published_level') is not None and not _falseish(resource.get('published_level')):
            raise WriteFailure('permission_denied', 'The meeting resource is not private and unpublished.')
        can = resource.get('can')
        if not isinstance(can, dict) or can.get('edit') is not True:
            raise WriteFailure('permission_denied', 'The evaluated meeting access state does not permit edits.')
        members = norm.get('members')
        if (not isinstance(members, list) or len(members) != 1
                or not isinstance(members[0], dict)
                or _native_id(members[0].get('id')) != owner_id):
            raise WriteFailure('permission_denied', 'The meeting is not limited to the exact owner membership.')
        if norm.get('groups') not in ([], None) or norm.get('guests') not in ([], None):
            raise WriteFailure('permission_denied', 'The meeting contains groups or guests outside the trusted scope.')
        if norm.get('group') is not None or norm.get('group_id') is not None:
            raise WriteFailure('permission_denied', 'The meeting group assignment is outside the trusted scope.')
        if norm.get('series_id') not in (0, None) or norm.get('recurrence_id') is not None:
            raise WriteFailure('permission_denied', 'The meeting series state is outside the trusted scope.')
        if norm.get('alternative_dates') is not None or norm.get('additional_dates') not in (None, []):
            raise WriteFailure('permission_denied', 'The meeting alternative dates are outside the trusted scope.')
        if norm.get('remote_option') != 'no_remote':
            raise WriteFailure('permission_denied', 'The meeting remote state is outside the trusted scope.')
        if norm.get('remote_url') is not None or norm.get('remote_url_description') is not None:
            raise WriteFailure('permission_denied', 'The meeting remote URL state is outside the trusted scope.')
        if not _falseish(norm.get('disable_remote_rsvp')):
            raise WriteFailure('permission_denied', 'The meeting remote RSVP state is outside the trusted scope.')
        for key in ('video_conference_enabled', 'enable_recording', 'enable_transcription',
                    'enable_ai_summary', 'starred_public_page'):
            if not _falseish(norm.get(key)):
                raise WriteFailure('permission_denied', 'The meeting media/publication state is outside the trusted scope.')

    def _read_snapshot(self, source, change, context, bounds, deadline, *, post_send=False, allow_cancelled=False):
        config = self.credentials(source, context)
        meeting_id = self._meeting_id(change)
        meeting_url = self._meeting_url(source, config, meeting_id)
        raw = self._request_json(source, change, context, 'GET', meeting_url + '?format=json', None,
                                 bounds, deadline, expected_status=200, post_send=post_send,
                                 allow_cancelled=allow_cancelled)
        _check_json_bounds(raw, bounds)
        if not isinstance(raw, dict) or not isinstance(raw.get('meeting'), dict):
            raise WriteFailure('provider_rejected', 'The Boardable document readback lacks a meeting object.')
        resource = raw.get('meeting_resource')
        if not isinstance(resource, dict):
            raise WriteFailure('provider_rejected', 'The Boardable document readback lacks meeting_resource.')
        if _native_id(resource.get('id')) != int(meeting_id):
            raise WriteFailure('permission_denied', 'meeting_resource.id differs from the trusted meeting.')
        if resource.get('url') != meeting_url:
            raise WriteFailure('permission_denied', 'meeting_resource.url differs from the exact trusted URL.')
        norm = _normalize_meeting(raw, config, source.url, expected_id=int(meeting_id), expected_url=meeting_url)
        self._validate_meeting_state(norm, resource, config)
        attachments = self._normalize_attachments(resource.get('attachments'), meeting_id, config, source.url, bounds)
        body = {'attachable_id': int(meeting_id), 'attachable_type': 'meeting', 'folder': 'root'}
        root_raw = self._request_json(source, change, context, 'POST', source.url + 'attachment-list', body,
                                      bounds, deadline, content_type='application/json',
                                      expected_status=200, post_send=post_send,
                                      allow_cancelled=allow_cancelled)
        _check_json_bounds(root_raw, bounds)
        root = self._normalize_root_list(root_raw, source.url, bounds)
        canonical_root_ids = {row['id'] for row in attachments if row['folder_id'] == 0}
        list_root_ids = {row['id'] for row in root['items']}
        if canonical_root_ids != list_root_ids:
            raise WriteFailure('conflict', 'The canonical root attachments and root list IDs disagree.')
        if not post_send:
            root_by_id = {row['id']: row for row in root['items']}
            for row in attachments:
                if row['folder_id'] == 0 and 'uuid' in row:
                    if _uuid_slug(root_by_id[row['id']]) != _uuid_slug(row):
                        raise WriteFailure('conflict', 'The canonical root attachment UUID slug differs from the root list.')
        before = {
            'meeting': norm,
            'meeting_resource': {'attachments': attachments},
            'root': root,
            'attachment_ids': sorted(row['id'] for row in attachments),
            'root_ids': sorted(row['id'] for row in root['items']),
        }
        return before

    def _upload_parts(self, meeting_id, part):
        return [
            {'kind': 'file', 'name': 'attachments[0][file]', 'part': deepcopy(part)},
            {'kind': 'field', 'name': 'attachments[0][type]', 'value': 'upload'},
            {'kind': 'field', 'name': 'attachable_type', 'value': 'meeting'},
            {'kind': 'field', 'name': 'attachable_id', 'value': meeting_id},
            {'kind': 'field', 'name': 'folder_id', 'value': '0'},
            {'kind': 'field', 'name': 'original_token', 'value': 'undefined'},
        ]

    def _find_attachment(self, attachments, identity):
        rows = [row for row in attachments if row.get('id') == identity]
        if len(rows) != 1:
            raise ValueError('The new native attachment is not uniquely present in the canonical view.')
        return rows[0]

    def _find_root_item(self, root, identity):
        rows = [row for row in root.get('items', []) if row.get('id') == identity]
        if len(rows) != 1:
            raise ValueError('The new native attachment is not uniquely present in the root list.')
        return rows[0]

    def _old_preserved(self, before, after):
        before_attachments = {row['id']: row for row in before['meeting_resource']['attachments']}
        after_attachments = {row['id']: row for row in after['meeting_resource']['attachments']}
        for identity, row in before_attachments.items():
            if after_attachments.get(identity) != row:
                return False
        before_root_meta = {key: value for key, value in before['root'].items() if key != 'items'}
        after_root_meta = {key: value for key, value in after['root'].items() if key != 'items'}
        if canonical_hash(before_root_meta) != canonical_hash(after_root_meta):
            return False
        before_root = {row['id']: row for row in before['root']['items']}
        after_root = {row['id']: row for row in after['root']['items']}
        for identity, row in before_root.items():
            if after_root.get(identity) != row:
                return False
        return True

    def _validate_detail(self, detail, identity, meeting_id, config, reference, filename, content_type,
                         expected_download_url, expected_document_url):
        if not isinstance(detail, dict):
            raise WriteFailure('provider_rejected', 'The independent document detail is not an object.')
        if _native_id(detail.get('id')) != identity:
            raise WriteFailure('permission_denied', 'The document detail native ID differs.')
        if _native_id(detail.get('attachable_id')) != int(meeting_id):
            raise WriteFailure('permission_denied', 'The document detail meeting association differs.')
        if detail.get('attachable_type') != _ATTACHABLE_TYPE:
            raise WriteFailure('permission_denied', 'The document detail attachable type differs.')
        if _native_id(detail.get('organization_id')) != _native_id(config.get('organization_id')):
            raise WriteFailure('permission_denied', 'The document detail organization differs.')
        if _native_id(detail.get('owner_id')) != _native_id(config.get('owner_id')):
            raise WriteFailure('permission_denied', 'The document detail owner differs.')
        if detail.get('folder_id') != 0:
            raise WriteFailure('permission_denied', 'The document detail is not in the root folder.')
        if detail.get('attached_type') != 'computer' or detail.get('document_id') != 0:
            raise WriteFailure('permission_denied', 'The document detail type is not the captured computer upload.')
        if detail.get('filename') != filename:
            raise WriteFailure('conflict', 'The document detail filename differs.')
        if detail.get('mime_type') != content_type:
            raise WriteFailure('conflict', 'The document detail MIME type differs.')
        if detail.get('file_size') != reference['byte_length']:
            raise WriteFailure('conflict', 'The document detail byte length differs.')
        declared = detail.get('downloadUrl')
        if not _same_url(declared, expected_download_url):
            raise WriteFailure('permission_denied', 'The document detail download URL is outside the exact route.')
        slug = _uuid_slug(detail)
        expected_doc = expected_document_url
        if not _same_url(detail.get('webUrl', detail.get('url')), expected_download_url):
            raise WriteFailure('permission_denied', 'The document detail URL is outside the exact route.')
        if expected_doc.split('/')[-2] != slug:
            raise WriteFailure('permission_denied', 'The document detail UUID short slug differs from the list route.')

    def _download_original(self, source, change, context, bounds, deadline, url, reference, *, post_send):
        self.authorize(source, change, context)
        if context.check_cancelled():
            raise WriteCancelled()
        config = self.credentials(source, context)
        headers = self._headers(config)
        headers['Accept'] = 'application/octet-stream'
        remaining = deadline - monotonic()
        if remaining <= 0:
            if post_send:
                raise AmbiguousWrite('The original attachment download deadline expired.')
            raise WriteFailure('deadline_exceeded', 'The original attachment download deadline expired.')
        try:
            response = self.transport.send(url, method='GET', body=None, headers=headers,
                                           byte_limit=bounds.transfer_bytes, deadline_seconds=remaining)
        except (OSError, TimeoutError, RuntimeError, ValueError):
            if post_send:
                raise AmbiguousWrite('The original attachment download could not be confirmed.') from None
            raise WriteFailure('provider_rejected', 'The original attachment download failed.') from None
        if not isinstance(response, WriteResponse) or len(response.content) > bounds.transfer_bytes:
            if post_send:
                raise AmbiguousWrite('The original attachment download response is invalid or oversized.')
            raise WriteFailure('provider_rejected', 'The original attachment download response is invalid.')
        if response.status != 200:
            if post_send:
                raise AmbiguousWrite('The original attachment download did not return exact bytes.')
            raise WriteFailure('provider_rejected', 'The original attachment download did not return exact bytes.')
        response_headers = getattr(response, 'headers', {}) or {}
        if any(str(key).lower() == 'location' for key in response_headers):
            raise AmbiguousWrite('The original attachment download attempted a redirect.')
        if len(response.content) != reference['byte_length']:
            raise WriteFailure('conflict', 'The original attachment byte length differs.')
        if hashlib.sha256(response.content).hexdigest() != reference['sha256']:
            raise WriteFailure('conflict', 'The original attachment SHA256 differs.')
        return response.content

    def _verify_candidate(self, source, change, prepared, context, bounds, deadline, snapshot,
                          identity, document_url, *, post_send=True):
        config = self.authorize(source, change, context)
        meeting_id = self._meeting_id(change)
        part = change.files[0]
        reference = part['reference']
        canonical = self._find_attachment(snapshot['meeting_resource']['attachments'], identity)
        root_row = self._find_root_item(snapshot['root'], identity)
        root_slug = _uuid_slug(root_row)
        if 'uuid' in canonical and _uuid_slug(canonical) != root_slug:
            raise WriteFailure('permission_denied', 'The canonical attachment UUID differs from the root list.')
        if canonical['folder_id'] != 0 or _native_id(canonical['owner_id']) != _native_id(config.get('owner_id')):
            raise WriteFailure('permission_denied', 'The new canonical attachment association differs.')
        if canonical.get('attached_type') != 'computer' or canonical.get('document_id') != 0:
            raise WriteFailure('permission_denied', 'The new canonical attachment type differs.')
        if canonical['filename'] != part['filename'] or canonical['file_size'] != reference['byte_length']:
            raise WriteFailure('conflict', 'The new canonical attachment metadata differs.')
        if canonical.get('mime_type') != part['content_type']:
            raise WriteFailure('conflict', 'The new canonical attachment MIME differs.')
        expected_download_url = _expected_download(source.url, identity, part['filename'])
        if not _same_url(_download_url(canonical), expected_download_url):
            raise WriteFailure('permission_denied', 'The new canonical attachment download route differs.')
        if root_row['filename'] != part['filename'] or root_row['file_size'] != reference['byte_length']:
            raise WriteFailure('conflict', 'The new root list attachment metadata differs.')
        if not _same_url(_download_url(root_row), expected_download_url):
            raise WriteFailure('permission_denied', 'The new root list attachment download route differs.')
        slug = _uuid_slug(root_row)
        expected_document_url = source.url + _DOCUMENT_SEGMENT + slug + '/data'
        if document_url != expected_document_url:
            raise WriteFailure('permission_denied', 'The persisted document URL differs from the native UUID slug.')
        detail = self._request_json(source, change, context, 'GET', document_url, None, bounds, deadline,
                                    expected_status=200, post_send=post_send)
        _check_json_bounds(detail, bounds)
        self._validate_detail(detail, identity, meeting_id, config, reference, part['filename'],
                              part['content_type'], expected_download_url, expected_document_url)
        if detail.get('filename') != canonical['filename'] or detail.get('file_size') != canonical['file_size']:
            raise WriteFailure('conflict', 'The document detail and canonical metadata disagree.')
        if _uuid_slug(detail) != slug:
            raise WriteFailure('permission_denied', 'The document detail UUID differs from the root list.')
        self._download_original(source, change, context, bounds, deadline, expected_download_url, reference,
                                post_send=post_send)
        if canonical_hash(snapshot['meeting']) != canonical_hash(prepared['before']['meeting']):
            raise WriteFailure('conflict', 'The meeting business/privacy/member state changed during upload.')
        if not self._old_preserved(prepared['before'], snapshot):
            raise WriteFailure('conflict', 'An old attachment record changed during upload.')
        return {
            'resource_id': str(identity),
            'meeting_id': meeting_id,
            'document_url': document_url,
            'association': {
                'attachable_type': _ATTACHABLE_TYPE,
                'attachable_id': int(meeting_id),
                'organization_id': _native_id(config.get('organization_id')),
                'owner_id': _native_id(config.get('owner_id')),
                'folder_id': 0,
            },
            'filename': part['filename'],
            'mime_type': part['content_type'],
            'original': {'sha256': reference['sha256'], 'size': reference['byte_length']},
        }

    def prepare(self, source, change, context, bounds, deadline):
        config = self.authorize(source, change, context)
        meeting_id = self._meeting_id(change)
        meeting_url = self._meeting_url(source, config, meeting_id)
        part = change.files[0]
        parts = self._upload_parts(meeting_id, part)
        self._multipart_body(parts, bounds)
        before = self._read_snapshot(source, change, context, bounds, deadline, post_send=False)
        fingerprint = canonical_hash(before)
        if change.expected_version is not None and change.expected_version != fingerprint:
            raise WriteFailure('conflict', 'The expected Boardable meeting document state differs from readback.')
        native = {'method': 'POST', 'url': source.url + 'attachments/upload', 'multipart': parts,
                  'files': [deepcopy(part)]}
        prepared = {
            'change': asdict(change),
            'before': before,
            'before_fingerprint': fingerprint,
            'meeting_id': meeting_id,
            'meeting_url': meeting_url,
            'file': deepcopy(part),
            'native': native,
            'conflict_semantics': 'preflight_normalized_snapshot_compare_not_atomic_upstream_cas',
        }
        _check_prepared_size(prepared, bounds)
        return prepared

    def apply(self, source, prepared, context, bounds, deadline, *, persist=None):
        change = WriteChange.from_dict(prepared['change'])
        config = self.authorize(source, change, context)
        meeting_id = self._meeting_id(change)
        meeting_url = self._meeting_url(source, config, meeting_id)
        part = change.files[0]
        self._validate_part(part)
        _check_prepared_size(prepared, bounds)
        expected_parts = self._upload_parts(meeting_id, part)
        expected_native = {'method': 'POST', 'url': source.url + 'attachments/upload',
                           'multipart': expected_parts, 'files': [deepcopy(part)]}
        if (prepared.get('native') != expected_native or prepared.get('file') != part
                or prepared.get('meeting_id') != meeting_id or prepared.get('meeting_url') != meeting_url):
            raise WriteFailure('plan_tampered', 'The prepared Boardable document request was altered.')
        if not isinstance(prepared.get('before'), dict) or prepared.get('before_fingerprint') != canonical_hash(prepared['before']):
            raise WriteFailure('plan_tampered', 'The prepared Boardable document snapshot is missing or altered.')
        current = self._read_snapshot(source, change, context, bounds, deadline, post_send=False)
        if canonical_hash(current) != prepared['before_fingerprint']:
            raise WriteFailure('conflict', 'The Boardable meeting document state changed after planning.')
        body, content_type = self._multipart_body(expected_parts, bounds)
        if len(body) > bounds.transfer_bytes:
            raise ValueError('The Boardable document upload exceeds transfer bounds.')
        if persist:
            if persist({'outbound_started': True, 'meeting_id': meeting_id, 'meeting_url': meeting_url}):
                raise WriteCancelled()
        elif context.check_cancelled():
            raise WriteCancelled()
        self.authorize(source, change, context)
        self._send_upload(source, change, context, bounds, deadline, body, content_type)
        try:
            after = self._read_snapshot(source, change, context, bounds, deadline, post_send=True,
                                        allow_cancelled=True)
        except (WriteFailure, ValueError, TypeError):
            raise AmbiguousWrite('The upload was observed but post-send native readback failed.') from None
        new_canonical = set(after['attachment_ids']) - set(current['attachment_ids'])
        new_root = set(after['root_ids']) - set(current['root_ids'])
        if new_canonical != new_root or len(new_canonical) != 1:
            raise AmbiguousWrite('The upload did not produce exactly one new native ID across both views.')
        identity = next(iter(new_canonical))
        try:
            self._find_attachment(after['meeting_resource']['attachments'], identity)
            root_row = self._find_root_item(after['root'], identity)
            slug = _uuid_slug(root_row)
            document_url = source.url + _DOCUMENT_SEGMENT + slug + '/data'
        except (TypeError, ValueError):
            raise AmbiguousWrite('The new native ID could not be bound to one safe document URL.') from None
        item = {'resource_id': str(identity), 'document_url': document_url, 'meeting_id': meeting_id,
                'meeting_url': meeting_url, 'outbound_started': True}
        cancelled = persist(item) if persist else context.check_cancelled()
        if cancelled or monotonic() >= deadline:
            raise AmbiguousWrite('The native document identity was retained before cancellation or deadline.')
        if not self._old_preserved(current, after):
            raise AmbiguousWrite('An old attachment record changed during upload; native identity retained.')
        try:
            receipt = self._verify_candidate(source, change, prepared, context, bounds, deadline, after,
                                             identity, document_url, post_send=True)
        except (WriteFailure, ValueError, TypeError):
            raise AmbiguousWrite('The native document identity was retained before exact verification completed.') from None
        return {'state': 'succeeded', 'resource_id': str(identity), 'document_url': document_url,
                'meeting_id': meeting_id, 'meeting_url': meeting_url, 'receipt': receipt,
                'reconciled': True}

    def reconcile(self, source, prepared, item, context, bounds, deadline):
        item = item or {}
        raw_id = item.get('resource_id')
        persisted_document_url = item.get('document_url')
        try:
            change = WriteChange.from_dict(prepared['change'])
            self.authorize(source, change, context)
            config = self.credentials(source, context)
            meeting_id = self._meeting_id(change)
            meeting_url = self._meeting_url(source, config, meeting_id)
            file_part = change.files[0]
            self._validate_part(file_part)
            _check_prepared_size(prepared, bounds)
            expected_parts = self._upload_parts(meeting_id, file_part)
            expected_native = {'method': 'POST', 'url': source.url + 'attachments/upload',
                               'multipart': expected_parts, 'files': [deepcopy(file_part)]}
            if (prepared.get('native') != expected_native or prepared.get('file') != file_part
                    or prepared.get('meeting_id') != meeting_id or prepared.get('meeting_url') != meeting_url):
                raise ValueError('The prepared Boardable document request is invalid.')
            if not isinstance(prepared.get('before'), dict) or prepared.get('before_fingerprint') != canonical_hash(prepared['before']):
                raise ValueError('The prepared before snapshot is missing or altered.')
            persisted = None
            if raw_id is not None:
                try:
                    value = str(raw_id) if type(raw_id) is int else raw_id
                    if not isinstance(value, str) or _SAFE_ID_RE.fullmatch(value) is None:
                        raise ValueError
                    persisted = int(value)
                except (TypeError, ValueError):
                    return {'state': 'uncertain', 'reconciled': True,
                            'reason': 'The persisted native document identity is invalid.'}
            snapshot = self._read_snapshot(source, change, context, bounds, deadline, post_send=True)
            new_canonical = set(snapshot['attachment_ids']) - set(prepared['before']['attachment_ids'])
            new_root = set(snapshot['root_ids']) - set(prepared['before']['root_ids'])
            if new_canonical != new_root or len(new_canonical) != 1:
                result = {'state': 'uncertain', 'reconciled': True,
                          'reason': 'Read-only recovery requires exactly one new native attachment ID.'}
                if persisted is not None:
                    result['resource_id'] = str(persisted)
                if isinstance(persisted_document_url, str):
                    result['document_url'] = persisted_document_url
                return result
            candidate = next(iter(new_canonical))
            if persisted is not None and persisted != candidate:
                return {'state': 'uncertain', 'resource_id': str(persisted), 'reconciled': True,
                        'reason': 'The persisted native document identity is not the sole new native ID.'}
            root_row = self._find_root_item(snapshot['root'], candidate)
            slug = _uuid_slug(root_row)
            document_url = source.url + _DOCUMENT_SEGMENT + slug + '/data'
            if persisted_document_url is not None and persisted_document_url != document_url:
                return {'state': 'uncertain', 'resource_id': str(candidate),
                        'document_url': persisted_document_url, 'reconciled': True,
                        'reason': 'The persisted document URL differs from the native UUID slug.'}
            if not self._old_preserved(prepared['before'], snapshot):
                return {'state': 'uncertain', 'resource_id': str(candidate), 'document_url': document_url,
                        'reconciled': True, 'reason': 'An old attachment record changed during recovery.'}
            try:
                receipt = self._verify_candidate(source, change, prepared, context, bounds, deadline,
                                                 snapshot, candidate, document_url, post_send=True)
            except (WriteFailure, ValueError, TypeError):
                return {'state': 'uncertain', 'resource_id': str(candidate), 'document_url': document_url,
                        'meeting_id': meeting_id, 'reconciled': True,
                        'reason': 'Read-only recovery retained the native ID but exact bytes or association did not verify.'}
            return {'state': 'succeeded', 'resource_id': str(candidate), 'document_url': document_url,
                    'meeting_id': meeting_id, 'meeting_url': meeting_url, 'receipt': receipt,
                    'reconciled': True}
        except (WriteFailure, ValueError, TypeError):
            result = {'state': 'uncertain', 'reconciled': True,
                      'reason': 'Read-only Boardable document reconciliation could not complete.'}
            if raw_id is not None:
                result['resource_id'] = str(raw_id)
            if isinstance(persisted_document_url, str):
                result['document_url'] = persisted_document_url
            return result
