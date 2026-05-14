
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, RedirectWarning, UserError
import requests
from datetime import datetime


class InheritedResCurrency(models.Model):
    _name = 'res.currency'
    _inherit = ['res.currency', 'mail.thread', 'mail.activity.mixin']