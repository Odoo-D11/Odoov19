
from odoo.addons.utils.models.utils import ( # type: ignore
    is_html_content_empty,
    format_html_to_sentence_case,
    convert_first_letter_to_uppercase,
)
import unicodedata


def _normalize_name(name):
    if not name:
        return name
    name = name.replace('ñ', '__enie__').replace('Ñ', '__ENIE__')
    name = unicodedata.normalize('NFD', name).encode('ascii', 'ignore').decode('ascii')
    name = name.replace('__enie__', 'ñ').replace('__ENIE__', 'Ñ')
    return name.title()
