
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError
from odoo.addons.utils.models.utils import ( # type: ignore
    is_html_content_empty,
    format_html_to_sentence_case,
    convert_first_letter_to_uppercase,
    is_valid_url,
)