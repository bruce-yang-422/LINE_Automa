"""Original duty roster as isolated test data; never imported during startup."""
from pathlib import Path
import re
from uuid import uuid4
import app
import duty


def seed(user):
    source = (Path(__file__).resolve().parents[2] / 'docs/LINE_NOTE_261006_1.md').read_text(encoding='utf-8')
    for line in source.splitlines():
        if not re.match(r'\| \d+ \|', line):
            continue
        code, nickname, name, department, _ = [v.strip() for v in line.strip('|').split('|')]
        if nickname == 'X':
            with app.database_connection() as conn:
                conn.execute('INSERT INTO duty_positions VALUES (?,?,?,?,1)', (uuid4().hex, user['organization_id'], code, int(code)))
            continue
        duty.save_person(user, {'full_name': name, 'display_name': nickname, 'department': department,
                              'floor': '2F', 'code': code, 'effective_from': '2026-01-01'})
    for line in source.splitlines():
        match = re.match(r'(\d+)\. \*\*(.+?)\*\*(.*)', line)
        if not match:
            continue
        code, name, description = match.groups()
        index = int(code)
        data = {'name': name, 'description': description.lstrip('：。'), 'effective_from': '2026-01-01',
                'kind': 'blank' if index == 1 else 'rest' if index == 14 else 'normal',
                'rotation': 'year' if index in (16, 17) else 'month', 'items': []}
        if index == 9:
            data['items'] = [
                {'content': '掃地、擦拭櫃子與桌椅灰塵', 'frequency': 'daily', 'reminder_time': '08:30', 'reminder_enabled': True},
                {'content': '拖地', 'frequency': 'weekly', 'weekdays': [1], 'reminder_time': '08:30', 'reminder_enabled': True},
            ]
        duty.save_task(user, data)
