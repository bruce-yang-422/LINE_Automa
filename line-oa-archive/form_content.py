"""Questionnaire illustration assets reuse the existing normalized image library."""
import json
import re
import sqlite3

import app
import composer
import forms


def image(conn, row, identifier):
    if not isinstance(identifier, str) or not re.fullmatch(r'[0-9a-f]{32}', identifier):
        raise ValueError('說明圖片識別碼不正確。')
    conn.row_factory = sqlite3.Row
    asset = conn.execute('SELECT 1 FROM upload_assets WHERE asset_id=? AND channel_id=? AND organization_id=?',
                         (identifier, row['channel_id'], row['organization_id'])).fetchone()
    path = app.BASE_DIR / 'data' / 'uploads' / (identifier + '.png')
    if not asset or not path.is_file():
        raise ValueError('說明圖片不存在或不屬於此問卷的 OA／組織。')
    return path


def validate_images(conn, row, questions):
    for q in questions:
        if q['type'] == 'content' and q['content']['kind'] == 'image':
            image(conn, row, q['content']['image_id'])


def upload(user, payload, *, preview=False, actor=None):
    user = forms.authorize(user, 'maintain', preview=preview)
    with app.database_connection() as conn:
        forms._find(conn, user, payload.get('form_id'))
    return composer.upload({'data': payload.get('data'), 'name': payload.get('name')}, user)


def admin_read(user, form_id, identifier, *, preview=False):
    user = forms.authorize(user, 'view', preview=preview)
    with app.database_connection() as conn:
        row = forms._find(conn, user, form_id)
        references = [q.get('content', {}).get('image_id') for q in json.loads(row['questions_json']) if q['type'] == 'content']
        if identifier not in references:
            forms.authorize(user, 'maintain', preview=preview)
        return image(conn, row, identifier).read_bytes()


def public_read(conn, row, identifier):
    references = [q.get('content', {}).get('image_id') for q in json.loads(row['questions_json']) if q['type'] == 'content' and q.get('content', {}).get('kind') == 'image']
    if identifier not in references:
        raise ValueError('此圖片不在問卷中。')
    return image(conn, row, identifier).read_bytes()
