"""Account-scoped portable archives. Never restore identity, billing or privileges.

Archives are untrusted input. Imports create private copies in one SQLite transaction;
ZIP entries are read by name, never extracted to client-supplied paths.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import sqlite3
import time
import uuid
import zipfile
import zlib
from urllib.parse import parse_qs, urlparse

FORMAT = 'homer-user-backup'
MAX_UPLOAD = 30 * 1024 * 1024
MAX_EXPANDED = 128 * 1024 * 1024
MAX_ROWS = 100_000
ROLE_FIELDS = ('name summary description cover_url tags opening_statement suggested_questions pre_prompt '
               'llm_model age_rating gender language extra_settings').split()
TABLE_FIELDS = {
    'conversations': 'id app_id app_name app_icon title last_message galgame_enabled global_preset_enabled pinned created_at updated_at version_id',
    'messages': 'id conversation_id role content created_at swipes swipe_index',
    'chat_memories': 'id app_id conversation_id title content keywords enabled pinned created_at updated_at last_used_at',
    'conversation_summaries': 'conversation_id app_id summary message_count created_at updated_at',
    'sillytavern_runtime_states': 'app_id conversation_id extension_settings_json worldbook_overrides_json regex_overrides_json script_trees_json mvu_state_json variables_json updated_at',
    'conversation_runtime_profiles': 'conversation_id app_id database_enabled prompt_enabled prompt_preset_id regex_enabled regex_preset_id status_mode strict_output update_frequency template_version revision created_at updated_at',
    'conversation_database_tables': 'id conversation_id table_key name columns_json single_row enabled sort_order revision created_at updated_at',
    'conversation_database_rows': 'id table_id conversation_id row_key row_index data_json source_message_id updated_by created_at updated_at',
    'conversation_preset_overrides': 'conversation_id preset_kind preset_id entry_id enabled updated_at',
    'conversation_worldbook_overrides': 'conversation_id source_key enabled patch_json updated_at',
}
TABLE_FIELDS = {k: v.split() for k, v in TABLE_FIELDS.items()}
SECRET_KEY = re.compile(r'(?:api_?key|access_?token|refresh_?token|auth_?token|authorization|cookie|password|secret|credentials|connector_key|api_base_url)|^token$', re.I)
SCOPE = {
    'included': ['人设', '自己创作的角色、历史版本和草稿', '云端会话、消息和候选回复', '会话设置、变量、记忆和数据库'],
    'excluded': ['密码和登录凭据', '积分、支付、排名和权限', '他人角色提示词', '未同步的本机草稿', '外部链接及独立图片/音频/Spine 文件（保留引用）'],
}


class BackupError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True, allow_nan=False).encode('utf-8')


def scrub(value, depth=0):
    if depth > 50:
        raise BackupError('备份结构层级过深')
    if isinstance(value, dict):
        return {k: scrub(v, depth + 1) for k, v in value.items()
                if isinstance(k, str) and not SECRET_KEY.search(k) and k not in ('__proto__', 'constructor', 'prototype')}
    if isinstance(value, list):
        return [scrub(v, depth + 1) for v in value]
    if value is None or type(value) in (str, int, bool):
        return value
    if isinstance(value, float):
        encoded(value)
        return value
    raise BackupError('备份包含不支持的数据类型')


def clean_row(row, fields):
    result = {key: row[key] for key in fields if key in row}
    for key, value in list(result.items()):
        if key.endswith('_json') or key == 'extra_settings':
            if value:
                try:
                    result[key] = encoded(scrub(json.loads(value) if isinstance(value, str) else value)).decode()
                except (ValueError, TypeError, RecursionError) as exc:
                    raise BackupError('备份中的结构化字段无效') from exc
    return scrub(result)


def schema(conn):
    conn.execute('''create table if not exists user_backup_imports (
        user_id text not null, digest text not null, result_json text not null, created_at integer not null,
        primary key(user_id,digest))''')


def export_data(store, user_id):
    with store.lock:
        # The Store serializes writers with this lock. A read transaction also
        # gives a coherent snapshot when another SQLite connection is writing.
        conn = store.conn
        conn.execute('begin')
        try:
            user = conn.execute('select persona_name,persona_desc from users where id=?', (user_id,)).fetchone()
            if user is None:
                raise BackupError('请先登录', 401)
            payload = {'persona': {'name': user[0] or '', 'description': user[1] or ''}, 'roles': [], 'tables': {}}
            roles = conn.execute("select * from local_apps where owner_user_id=? and source='user' order by id", (user_id,)).fetchall()
            for row in roles:
                role = clean_row(dict(row), ['id', 'current_version_id', 'created_at', 'updated_at'] + ROLE_FIELDS)
                role['versions'] = []
                for v in conn.execute("select * from content_versions where entity_type='character' and entity_id=? order by version_no", (row['id'],)):
                    v = dict(v)
                    role['versions'].append({**clean_row(v, ['id', 'version_no', 'version_name', 'author_description', 'created_at']),
                                             'snapshot': clean_row(json.loads(v['snapshot_json']), ROLE_FIELDS)})
                draft = conn.execute("select snapshot_json from content_drafts where entity_type='character' and entity_id=? and owner_user_id=?", (row['id'], user_id)).fetchone()
                role['draft'] = clean_row(json.loads(draft[0]), ROLE_FIELDS) if draft else None
                payload['roles'].append(role)
            for table, fields in TABLE_FIELDS.items():
                sql = f'select * from {table} where user_id=?'
                if table == 'chat_memories':
                    sql += " and (coalesce(conversation_id,'')='' or conversation_id in (select id from conversations where user_id=?))"
                elif table != 'conversations':
                    sql += ' and conversation_id in (select id from conversations where user_id=?)'
                rows = conn.execute(sql, (user_id,) if table == 'conversations' else (user_id, user_id)).fetchall()
                payload['tables'][table] = [clean_row(dict(row), fields) for row in rows]
            doc = {'format': FORMAT, 'schema_version': 1, 'captured_at': int(time.time()*1000), 'scope': SCOPE, 'payload': payload}
            validate(doc)
            return doc
        finally:
            conn.rollback()


def pack(doc):
    raw = encoded(doc)
    if len(raw) > MAX_EXPANDED:
        raise BackupError('个人数据超过单个备份上限，请联系管理员分批导出', 413)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr('backup.json', raw)
        z.writestr('README.txt', '惑梦个人备份。请在“我的 → 设置 → 本地备份”预览并导入。\n含私人聊天，请妥善保管。\n独立媒体文件保留链接引用；积分、支付和权限不参与恢复。\n'.encode('utf-8'))
    if buf.tell() > MAX_UPLOAD:
        raise BackupError('压缩后超过 30 MB，请联系管理员分批导出', 413)
    return buf.getvalue()


def unpack(raw):
    if not raw or len(raw) > MAX_UPLOAD:
        raise BackupError('请选择不超过 30 MB 的备份文件', 413)
    try:
        if raw.lstrip().startswith(b'{'):
            data = raw
        else:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                names = z.namelist()
                if len(names) != len(set(names)) or not 1 <= len(names) <= 2 or not set(names) <= {'backup.json', 'README.txt'} or 'backup.json' not in names:
                    raise BackupError('备份压缩包结构不正确')
                if sum(i.file_size for i in z.infolist()) > MAX_EXPANDED or any(i.flag_bits & 1 for i in z.infolist()):
                    raise BackupError('备份展开后过大或被加密', 413)
                with z.open('backup.json') as f:
                    data = f.read(MAX_EXPANDED + 1)
                if len(data) > MAX_EXPANDED:
                    raise BackupError('备份展开后过大', 413)
        def pairs(items):
            result = {}
            for key, val in items:
                if key in result:
                    raise BackupError('备份存在重复字段')
                result[key] = val
            return result
        doc = json.loads(data, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(BackupError('备份数字无效')))
        validate(doc)
        return doc
    except BackupError:
        raise
    except (ValueError, TypeError, KeyError, zipfile.BadZipFile, UnicodeError, RecursionError, RuntimeError, EOFError, zlib.error) as exc:
        raise BackupError('文件损坏或不是支持的惑梦备份') from exc


def validate(doc):
    if not isinstance(doc, dict) or doc.get('format') != FORMAT or type(doc.get('schema_version')) is not int or doc['schema_version'] != 1:
        raise BackupError('不支持此备份格式或版本')
    p = doc.get('payload')
    if not isinstance(p, dict) or not isinstance(p.get('persona'), dict) or not isinstance(p.get('roles'), list) or not isinstance(p.get('tables'), dict):
        raise BackupError('备份内容不完整')
    if set(p['tables']) != set(TABLE_FIELDS):
        raise BackupError('备份数据表不完整或包含不支持的类别')
    persona = p['persona']
    if not isinstance(persona.get('name'), str) or len(persona['name']) > 60 or not isinstance(persona.get('description'), str) or len(persona['description']) > 4000:
        raise BackupError('人设格式或长度不正确')
    ids = {}
    total = 0
    for table, rows in [('roles', p['roles']), *p['tables'].items()]:
        if not isinstance(rows, list):
            raise BackupError('备份记录格式不正确')
        total += len(rows)
        if total > MAX_ROWS or (table == 'roles' and len(rows) > 2000):
            raise BackupError('备份记录数量超过限制', 413)
        ids[table] = set()
        for row in rows:
            if not isinstance(row, dict):
                raise BackupError('备份记录格式不正确')
            if table == 'roles' or 'id' in TABLE_FIELDS.get(table, []):
                value = row.get('id')
                if not isinstance(value, str) or not value or len(value) > 200 or value in ids[table]:
                    raise BackupError('备份记录 ID 缺失或重复')
                ids[table].add(value)
            if table != 'roles':
                for key, value in row.items():
                    if key not in TABLE_FIELDS[table] or (value is not None and type(value) not in (str, int, bool)):
                        raise BackupError('备份含不支持的数据字段')
                    if isinstance(value, str) and len(value) > 16_000_000:
                        raise BackupError('单条记录超过限制', 413)
                    if type(value) is int and not -(2**63) <= value < 2**63:
                        raise BackupError('备份数字超出有效范围')
            else:
                versions = row.get('versions')
                if not isinstance(versions, list) or len(versions) > 200:
                    raise BackupError('角色版本数量或格式不正确')
                seen, nums = set(), set()
                for v in versions:
                    if not isinstance(v, dict) or not isinstance(v.get('snapshot'), dict) or not isinstance(v.get('id'), str) or not v['id'] or v['id'] in seen:
                        raise BackupError('角色版本格式或 ID 不正确')
                    if type(v.get('version_no')) is not int or v['version_no'] < 1 or v['version_no'] in nums:
                        raise BackupError('角色版本号无效或重复')
                    seen.add(v['id']); nums.add(v['version_no'])
                    clean_row(v['snapshot'], ROLE_FIELDS)
                if row.get('current_version_id') and row['current_version_id'] not in seen:
                    raise BackupError('角色当前版本在备份中不存在')
                if row.get('draft') is not None and not isinstance(row['draft'], dict):
                    raise BackupError('角色草稿格式不正确')
                clean_row(row, ROLE_FIELDS)
    for table, rows in p['tables'].items():
        for row in rows:
            global_memory = table == 'chat_memories' and not row.get('conversation_id')
            if table != 'conversations' and not global_memory and row.get('conversation_id') not in ids['conversations']:
                raise BackupError('备份存在无所属会话的记录')
            if table == 'conversation_database_rows' and row.get('table_id') not in ids['conversation_database_tables']:
                raise BackupError('备份数据库行缺少所属表')
            if table == 'messages' and row.get('role') not in ('user', 'assistant', 'system'):
                raise BackupError('消息角色无效')
            clean_row(row, TABLE_FIELDS[table])
    scrub(p)


def summary(doc):
    p = doc['payload']
    return {'captured_at': doc.get('captured_at'), 'roles': len(p['roles']),
            'versions': sum(len(r['versions']) for r in p['roles']),
            'conversations': len(p['tables']['conversations']), 'messages': len(p['tables']['messages']),
            'memories': len(p['tables']['chat_memories']), 'scope': SCOPE}


def restore(store, user_id, doc, *, restore_persona=False, can_play, normalize_model, check_role):
    validate(doc)
    p = doc['payload']
    # Existing entitlement helpers can initialize farm state and commit. Run
    # them before the import transaction, never inside its atomic write phase.
    for role in p['roles']:
        check_role(clean_row(role, ROLE_FIELDS))
        for v in role['versions']:
            check_role(clean_row(v['snapshot'], ROLE_FIELDS))
        if role.get('draft') is not None:
            check_role(clean_row(role['draft'], ROLE_FIELDS))
    # Digest describes content, not capture time. Downloading unchanged data again
    # must not create another set of copies.
    digest = hashlib.sha256(encoded(p)).hexdigest()
    result = summary(doc)
    ts = int(time.time()*1000)
    with store.lock:
        c = store.conn
        schema(c)
        c.commit()
        c.execute('begin immediate')
        try:
            previous = c.execute('select result_json from user_backup_imports where user_id=? and digest=?', (user_id, digest)).fetchone()
            if previous:
                c.rollback()
                return {**json.loads(previous[0]), 'already_imported': True}
            role_map, version_map, conv_map, table_map, message_map = {}, {}, {}, {}, {}
            def insert(table, row):
                fields = list(row)
                c.execute(f'insert into {table} ({",".join(fields)}) values ({",".join("?" for _ in fields)})', tuple(row[k] for k in fields))
            def private_role(source):
                r = clean_row(source, ROLE_FIELDS)
                for field in ROLE_FIELDS:
                    val = r.get(field)
                    if field in ('age_rating', 'gender'):
                        if val is not None and type(val) not in (int, bool):
                            raise BackupError('角色数字字段无效')
                    elif val is not None and not isinstance(val, str):
                        raise BackupError('角色文本字段无效')
                r.update(source='user', owner_user_id=user_id, is_public=0, status='published',
                         sort_weight=0, official_recommended=0, api_base_url='',
                         llm_model=normalize_model(r.get('llm_model')), created_at=ts, updated_at=ts)
                return r
            for role in p['roles']:
                rid = 'user-' + uuid.uuid4().hex[:16]
                role_map[role['id']] = rid
                row = private_role(role)
                row.update(id=rid, display_id=store._next_local_app_display_id_locked())
                insert('local_apps', row)
                for v in role['versions']:
                    vid = 'cver_' + uuid.uuid4().hex[:16]
                    if v['id'] in version_map:
                        raise BackupError('角色之间存在重复版本 ID')
                    version_map[v['id']] = vid
                    snapshot = private_role(v['snapshot'])
                    snapshot.pop('created_at'); snapshot.pop('updated_at')
                    snapshot['display_id'] = row['display_id']
                    blob = encoded(snapshot)
                    insert('content_versions', {'id': vid, 'entity_type': 'character', 'entity_id': rid,
                        'version_no': v['version_no'], 'version_name': str(v.get('version_name') or '恢复版本')[:80],
                        'author_description': str(v.get('author_description') or '')[:4000],
                        'snapshot_json': blob.decode(), 'content_hash': hashlib.sha256(blob).hexdigest(),
                        'created_by': user_id, 'created_at': int(v.get('created_at') or ts)})
                if role.get('current_version_id'):
                    c.execute('update local_apps set current_version_id=? where id=?', (version_map[role['current_version_id']], rid))
                if role.get('draft') is not None:
                    insert('content_drafts', {'entity_type': 'character', 'entity_id': rid, 'owner_user_id': user_id,
                        'snapshot_json': encoded(private_role(role['draft'])).decode(), 'updated_at': ts})
            unavailable = 0
            def resolve_role(old, name='存档角色'):
                nonlocal unavailable
                if not old:
                    return ''
                if old in role_map:
                    return role_map[old]
                existing = c.execute('select * from local_apps where id=?', (old,)).fetchone()
                if existing and can_play(existing, user_id):
                    role_map[old] = old
                else:
                    # The user's text remains readable even if a third-party card
                    # was removed. No third-party prompts or access are recovered.
                    rid = 'user-' + uuid.uuid4().hex[:16]
                    row = private_role({'name': str(name)[:100] + '（存档）', 'description': '原角色不可用，此私有角色仅保存导入的历史消息。'})
                    row.update(id=rid, display_id=store._next_local_app_display_id_locked())
                    insert('local_apps', row)
                    role_map[old] = rid
                    unavailable += 1
                return role_map[old]
            for original in p['tables']['conversations']:
                row = clean_row(original, TABLE_FIELDS['conversations'])
                new = str(uuid.uuid4()); conv_map[row['id']] = new
                row['id'], row['user_id'] = new, user_id
                row['app_id'] = resolve_role(row.get('app_id'), row.get('app_name') or '存档角色')
                if not row['app_id']:
                    raise BackupError('会话缺少角色引用')
                version = row.get('version_id') or ''
                if version in version_map:
                    row['version_id'] = version_map[version]
                    if not c.execute('select 1 from content_versions where id=? and entity_id=?', (row['version_id'], row['app_id'])).fetchone():
                        raise BackupError('会话版本与角色不匹配')
                elif version:
                    ok = c.execute("select 1 from content_versions where id=? and entity_type='character' and entity_id=?", (version, row['app_id'])).fetchone()
                    row['version_id'] = version if ok else ''
                insert('conversations', row)
            for row in p['tables']['messages']:
                message_map[row['id']] = str(uuid.uuid4())
            for row in p['tables']['conversation_database_tables']:
                table_map[row['id']] = str(uuid.uuid4())
            for table, rows in p['tables'].items():
                if table == 'conversations':
                    continue
                for original in rows:
                    row = clean_row(original, TABLE_FIELDS[table])
                    row['user_id'] = user_id
                    row['conversation_id'] = conv_map[row['conversation_id']] if row.get('conversation_id') else ''
                    if 'id' in row:
                        row['id'] = message_map[original['id']] if table == 'messages' else table_map[original['id']] if table == 'conversation_database_tables' else str(uuid.uuid4())
                    if 'table_id' in row:
                        row['table_id'] = table_map[row['table_id']]
                    if row.get('source_message_id'):
                        row['source_message_id'] = message_map.get(row['source_message_id'], '')
                    if 'app_id' in row:
                        # Always bind subordinate state to its recovered conversation.
                        row['app_id'] = c.execute('select app_id from conversations where id=?', (row['conversation_id'],)).fetchone()[0] if row['conversation_id'] else resolve_role(row.get('app_id'))
                    insert(table, row)
            if restore_persona:
                c.execute('update users set persona_name=?,persona_desc=?,updated_at=? where id=?',
                          (p['persona']['name'], p['persona']['description'], ts, user_id))
            result.update(already_imported=False, persona_restored=bool(restore_persona), unavailable_roles=unavailable,
                          first_conversation_id=next(iter(conv_map.values()), ''), first_role_id=next(iter(role_map.values()), ''))
            insert('user_backup_imports', {'user_id': user_id, 'digest': digest, 'result_json': encoded(result).decode(), 'created_at': ts})
            c.commit()
            return result
        except Exception:
            c.rollback()
            raise


def handle(handler, path, query, *, can_play, normalize_model, check_role, public_origin):
    prefix = '/console/api/web/user-backup/'
    if not path.startswith(prefix):
        return False
    try:
        user = handler.authenticated_user()
        if not user:
            raise BackupError('请先登录后使用备份', 401)
        action = path[len(prefix):]
        if action == 'download' and handler.command == 'GET':
            raw = pack(export_data(handler.store, user['id']))
            handler.send_response(200)
            handler.send_header('Content-Type', 'application/zip')
            handler.send_header('Content-Disposition', 'attachment; filename="homer-backup-' + time.strftime('%Y%m%d-%H%M%S') + '.zip"')
            handler.send_header('Content-Length', str(len(raw)))
            handler.send_header('Cache-Control', 'private, no-store')
            handler.send_header('X-Content-Type-Options', 'nosniff')
            handler.send_header('Connection', 'close')
            handler.end_headers()
            handler.wfile.write(raw)
            handler.close_connection = True
            return True
        if action not in ('preview', 'restore') or handler.command != 'POST':
            raise BackupError('不支持的备份操作', 405)
        # Custom header + strict origin check protects Cookie-authenticated imports.
        origin = handler.headers.get('Origin', '').rstrip('/')
        host_origin = urlparse(public_origin)
        if handler.headers.get('X-Homer-Backup') != '1' or (origin and origin != f'{host_origin.scheme}://{host_origin.netloc}') or handler.headers.get('Sec-Fetch-Site') == 'cross-site':
            raise BackupError('请从惑梦备份页面发起操作', 403)
        length = int(handler.headers.get('Content-Length', '0'))
        if not 0 < length <= MAX_UPLOAD:
            raise BackupError('备份文件大小必须在 30 MB 以内', 413)
        raw = handler.rfile.read(length)
        if len(raw) != length:
            raise BackupError('备份上传不完整')
        doc = unpack(raw)
        if action == 'preview':
            result = summary(doc)
        else:
            result = restore(handler.store, user['id'], doc,
                restore_persona=parse_qs(query).get('persona', ['0']) == ['1'],
                can_play=can_play, normalize_model=normalize_model,
                check_role=lambda row: check_role(user['id'], row))
        handler.send_json(200, {'result': 'success', 'data': result})
    except BackupError as exc:
        handler.send_json(exc.status, {'result': 'failure', 'message': str(exc)})
    except (ValueError, TypeError, KeyError, OverflowError, sqlite3.IntegrityError):
        handler.send_json(400, {'result': 'failure', 'message': '备份字段或关联关系无效，未恢复任何内容'})
    except PermissionError:
        handler.send_json(403, {'result': 'failure', 'message': '当前账号没有恢复该角色内容的权限'})
    except Exception as exc:
        handler.log_message('user backup failed: %s', type(exc).__name__)
        handler.send_json(500, {'result': 'failure', 'message': '备份操作未完成，请稍后重试'})
    return True
