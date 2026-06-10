from django import template

register = template.Library()


@register.filter
def get_item(value, key):
    if isinstance(value, dict):
        return value.get(key, '')
    return ''


@register.filter
def is_checkbox(field):
    return getattr(getattr(field, 'field', None), 'widget', None).__class__.__name__ == 'CheckboxInput'


@register.filter
def to_percent(value, digits=1):
    try:
        return f"{float(value) * 100:.{int(digits)}f}%"
    except Exception:
        return 'н/д'


@register.filter
def prettify_key(value):
    mapping = {
        'standard': 'Класичні ознаки',
        'fractal': 'Фрактальні ознаки',
        'combined': 'Комбіновані ознаки',
        'compare': 'Порівняння ознак',
    }
    key = str(value)
    if key in mapping:
        return mapping[key]
    text = key.replace('_', ' ')
    return text[:1].upper() + text[1:]


@register.filter
def list_index(value, idx):
    try:
        return value[int(idx)]
    except Exception:
        return ""
