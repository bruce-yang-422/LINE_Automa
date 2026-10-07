"""Shared form definitions and server validation; limits and regexes have one source."""
import copy
import json
import math
import re
from pathlib import Path

import limits

RULES = json.loads(Path(__file__).with_name('form_rules.json').read_text(encoding='utf-8'))


class DefinitionError(ValueError):
    def __init__(self, errors):
        self.errors = errors
        super().__init__('題目設定不正確：' + '；'.join(errors.values()))


def configuration():
    return {**copy.deepcopy(RULES), 'limits': limits.as_dict()}


def trim(value):
    space = RULES['patterns']['space']
    return re.sub(f'^{space}+|{space}+$', '', value)


def matches(name, value):
    pattern = RULES['patterns'][name].replace(r'\s', RULES['patterns']['space'][1:-1])
    return bool(re.fullmatch(pattern, value, re.ASCII))


def number(value):
    if type(value) not in (int, float, str):
        return None
    if isinstance(value, str):
        if not matches('number', trim(value)):
            return None
        value = trim(value)
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, OverflowError):
        return None


def valid_date(value):
    if not isinstance(value, str) or not matches('date', value):
        return False
    from datetime import date
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def validate_questions(questions):
    errors, ids = {}, set()
    if not isinstance(questions, list) or len(questions) > limits.FORM_QUESTIONS_MAX:
        raise DefinitionError({'_form': '題目數量超過上限或格式不正確。'})
    for index, q in enumerate(questions):
        key = str(index)
        try:
            if not isinstance(q, dict):
                raise ValueError('題目格式不正確。')
            identifier = q.get('id')
            if not isinstance(identifier, str) or len(identifier) > limits.FORM_NAME_MAX or not matches('identifier', identifier) or identifier in ids or identifier in RULES['reserved_ids']:
                raise ValueError('題目識別碼必須唯一且有效。')
            ids.add(identifier)
            key = identifier
            kind = q.get('type')
            if not isinstance(kind, str) or kind not in RULES['types']:
                raise ValueError('題型不正確。')
            for name, maximum, required in [('title', limits.FORM_TEXT_MAX, True), ('description', limits.FORM_TEXT_MAX, False)]:
                value = q.get(name, '')
                if not isinstance(value, str) or len(value) > maximum or (required and not trim(value)):
                    raise ValueError('請填寫題目標題與有效說明。')
            if type(q.get('required', False)) is not bool or type(q.get('allow_other', False)) is not bool:
                raise ValueError('必填或其他選項設定不正確。')
            if q.get('allow_other') and kind not in {'single_choice', 'multiple_choice'}:
                raise ValueError('只有單選與多選可開啟其他。')
            if kind == 'section' and q.get('required'):
                raise ValueError('分區標題不能設為必填。')
            options = q.get('options', [])
            if not isinstance(options, list) or len(options) > limits.FORM_OPTIONS_MAX or (kind in RULES['choice_types'] and not options):
                raise ValueError('選項數量不正確。')
            option_ids = set()
            for option in options:
                if not isinstance(option, dict):
                    raise ValueError('選項格式不正確。')
                oid, label = option.get('id'), option.get('label')
                if not isinstance(oid, str) or len(oid) > limits.FORM_NAME_MAX or not matches('identifier', oid) or oid in option_ids or oid in RULES['reserved_ids']:
                    raise ValueError('選項識別碼必須唯一且有效。')
                if not isinstance(label, str) or not trim(label) or len(label) > limits.FORM_TEXT_MAX:
                    raise ValueError('請填寫有效選項文字。')
                option_ids.add(oid)
            v = q.get('validation', {'enabled': False})
            if not isinstance(v, dict) or type(v.get('enabled', False)) is not bool:
                raise ValueError('答案驗證開關不正確。')
            if not isinstance(v.get('message', ''), str) or len(v.get('message', '')) > limits.FORM_TEXT_MAX:
                raise ValueError('驗證提示過長或格式不正確。')
            allowed_keys = RULES['validation_keys'].get(kind, ['enabled', 'message'])
            if any(k not in allowed_keys for k in v) or (v.get('enabled') and kind not in RULES['validation_keys']):
                raise ValueError('此題型不支援指定的驗證條件。')
            if kind in RULES['validation_keys']:
                _validate_conditions(kind, v, len(options) + int(q.get('allow_other', False)))
            if kind == 'rating':
                rating = q.get('rating', RULES['rating_default'])
                if not isinstance(rating, dict) or any(type(rating.get(k)) is not int or number(rating.get(k)) is None for k in ('min', 'max')) or rating['min'] > rating['max']:
                    raise ValueError('評分範圍需為整數，且最小值不可大於最大值。')
                for k in ('lower_label', 'upper_label'):
                    if not isinstance(rating.get(k, ''), str) or len(rating.get(k, '')) > limits.FORM_TEXT_MAX:
                        raise ValueError('評分說明不正確。')
            if kind == 'attachment':
                attachment = q.get('attachment', {})
                allowed = {ext for group in RULES['attachment_groups'].values() for ext in group}
                extensions = attachment.get('extensions') if isinstance(attachment, dict) else None
                if not isinstance(extensions, list) or not extensions or any(not isinstance(ext, str) or ext not in allowed for ext in extensions) or len(set(extensions)) != len(extensions):
                    raise ValueError('請選擇支援的附件格式。')
                for name, maximum in [('max_files', limits.FORM_ATTACHMENTS_PER_QUESTION), ('max_file_bytes', limits.FORM_ATTACHMENT_MAX_BYTES), ('max_total_bytes', limits.FORM_ATTACHMENT_TOTAL_MAX_BYTES)]:
                    if type(attachment.get(name)) is not int or not 1 <= attachment[name] <= maximum:
                        raise ValueError('附件限制超過平台上限或格式不正確。')
        except ValueError as exc:
            errors[key] = str(exc)
    if errors:
        raise DefinitionError(errors)
    return copy.deepcopy(questions)


def _validate_conditions(kind, v, option_count):
    if kind == 'short_text':
        if not isinstance(v.get('format', 'none'), str) or v.get('format', 'none') not in RULES['formats'] or not isinstance(v.get('phone_mode', 'tw_mobile'), str) or v.get('phone_mode', 'tw_mobile') not in RULES['phone_modes'] or type(v.get('allow_extension', False)) is not bool:
            raise ValueError('文字格式或電話驗證設定不正確。')
    if kind == 'number' and type(v.get('integer', False)) is not bool:
        raise ValueError('整數設定不正確。')
    pairs = [('min_length', 'max_length', limits.FORM_TEXT_MAX)] if kind in RULES['text_types'] else [('count_min', 'count_max', option_count)] if kind == 'multiple_choice' else []
    for low, high, maximum in pairs:
        for key in (low, high):
            if key in v and (type(v[key]) is not int or not 0 <= v[key] <= maximum):
                raise ValueError('文字長度或選取數量超過允許範圍。')
        if v.get(low, 0) > v.get(high, maximum):
            raise ValueError('最少值不可大於最多值。')
    if kind == 'multiple_choice' and 'count_exact' in v:
        value = v['count_exact']
        if type(value) is not int or not 0 <= value <= option_count or not v.get('count_min', 0) <= value <= v.get('count_max', option_count):
            raise ValueError('恰好數量與可選數量或最少／最多設定矛盾。')
    if kind == 'number':
        for key in ('min', 'max'):
            if key in v and (type(v[key]) not in (int, float) or number(v[key]) is None):
                raise ValueError('數字上下限不正確。')
        if 'min' in v and 'max' in v and v['min'] > v['max']:
            raise ValueError('最小值不可大於最大值。')
        if v.get('integer') and 'min' in v and 'max' in v and math.ceil(v['min']) > math.floor(v['max']):
            raise ValueError('此範圍沒有可填寫的整數。')
    if kind == 'date':
        if any(not valid_date(v[k]) for k in ('date_min', 'date_max') if k in v):
            raise ValueError('日期範圍不正確。')
        if v.get('date_min', '') > v.get('date_max', '9999-12-31'):
            raise ValueError('最早日期不可晚於最晚日期。')


def validate_answers(questions, answers):
    """Return per-question errors. Never coerce or mutate a submitted answer."""
    if not isinstance(answers, dict):
        return {'_form': RULES['messages']['structure']}
    errors = {}
    active = {q['id'] for q in questions if q['type'] != 'section'}
    if any(key not in active for key in answers):
        errors['_form'] = RULES['messages']['unknown']
    for q in questions:
        if q['type'] == 'section':
            continue
        code, custom = _answer_error(q, answers.get(q['id']))
        if code:
            v = q.get('validation', {})
            errors[q['id']] = v.get('message') if custom and v.get('message') else RULES['messages'][code]
    return errors


def _answer_error(q, value):
    kind, v = q['type'], q.get('validation', {})
    enabled = v.get('enabled', False)
    other, selections = '', None
    if kind in RULES['choice_types'] and value is not None:
        multiple = kind == 'multiple_choice'
        if isinstance(value, dict):
            if any(k not in ({'option_ids', 'other'} if multiple else {'option_id', 'other'}) for k in value):
                return 'structure', False
            selected = value.get('option_ids' if multiple else 'option_id', [] if multiple else '')
            other = value.get('other', '')
        else:
            selected = value
        selections = selected if multiple else ([] if selected == '' else [selected])
        if not isinstance(selections, list) or any(not isinstance(item, str) for item in selections) or len(set(selections)) != len(selections) or not isinstance(other, str):
            return 'structure', False
        valid = {option['id'] for option in q['options']}
        if q.get('allow_other'):
            valid.add(RULES['other_id'])
        if any(item not in valid for item in selections):
            return 'choice', False
        if len(other) > limits.FORM_TEXT_MAX:
            return 'text_limit', False
        if RULES['other_id'] in selections and not trim(other):
            return 'other', False
        if trim(other) and RULES['other_id'] not in selections:
            return 'choice', False
    empty = value is None or (isinstance(value, str) and not trim(value)) or (selections is not None and not selections) or (kind == 'attachment' and value == [])
    if empty:
        return ('required' if q.get('required') else None), False
    if kind in RULES['text_types']:
        if not isinstance(value, str):
            return 'text', False
        if len(value) > limits.FORM_TEXT_MAX:
            return 'text_limit', False
        if enabled:
            if len(value) < v.get('min_length', 0) or len(value) > v.get('max_length', limits.FORM_TEXT_MAX):
                return 'length', True
            fmt = v.get('format', 'none')
            if fmt == 'email' and not matches('email', trim(value)):
                return 'email', True
            if fmt == 'phone':
                mode = v.get('phone_mode', 'tw_mobile')
                phone = re.sub(RULES['patterns']['space'] + '|-', '', value)
                extension = re.search(RULES['patterns']['extension'], phone, re.ASCII)
                if extension:
                    if mode != 'tw_landline' or not v.get('allow_extension'):
                        return 'phone', True
                    phone = phone[:extension.start()]
                if not matches(mode, phone):
                    return 'phone', True
    elif kind in {'number', 'rating'}:
        numeric = number(value)
        if numeric is None:
            return 'number', False
        conditions = q.get('rating', RULES['rating_default']) if kind == 'rating' else v if enabled else {}
        if (kind == 'rating' or conditions.get('integer')) and not numeric.is_integer():
            return 'integer', kind != 'rating'
        if ('min' in conditions and numeric < number(conditions['min'])) or ('max' in conditions and numeric > number(conditions['max'])):
            return 'range', kind != 'rating'
    elif kind == 'multiple_choice' and enabled:
        count = len(selections)
        if count < v.get('count_min', 0) or count > v.get('count_max', len(q['options']) + int(q.get('allow_other', False))) or ('count_exact' in v and count != v['count_exact']):
            return 'count', True
    elif kind == 'date':
        if not valid_date(value):
            return 'date', False
        if enabled and (value < v.get('date_min', '0001-01-01') or value > v.get('date_max', '9999-12-31')):
            return 'date_range', True
    elif kind == 'time':
        if not isinstance(value, str) or not matches('time', value):
            return 'time', False
    elif kind == 'attachment':
        # Attachment IDs must be verified by the invitation storage layer in phase four.
        return 'attachment', False
    return None, False
