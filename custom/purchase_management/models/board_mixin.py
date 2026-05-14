from odoo import models, fields, api, _


class PurchaseBoardMixin(models.AbstractModel):
    _name = 'purchase.board.mixin'
    _description = 'Mixin para tableros de productos y cotizaciones'

    def _show_error_notification(self, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _('Error'), 'message': message, 'type': 'danger', 'sticky': False}
        }

    def _open_wizard(self, res_model, context):
        return {
            'name': 'Odoo',
            'type': 'ir.actions.act_window',
            'res_model': res_model,
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    def _get_product_channel_name(self):
        return f"request_quotation_products{self.id}"

    @api.model
    def get_board_data(self, record_id):
        """Endpoint unificado que retorna datos para ProductBoard y QuotationBoard en una sola llamada RPC."""
        if not record_id:
            return {'products': [], 'quotations': [], 'quotation_products': []}

        products = self.env['request.product.quotation.line'].search_read(
            [('request_quotation_id', '=', record_id)],
            ['id', 'qty', 'display_type'],
        )

        quotations = self.env['quotation.quotation'].search_read(
            [('request_quotation_id', '=', record_id)],
            ['id', 'write_date', 'product_line_ids', 'supplier_name',
             'validity_date', 'delivery_date', 'payment_term',
             'currency_id', 'observation_ids', 'trm',
             'purchase_observation_recommendation_ids'],
        )

        all_line_ids = []
        for q in quotations:
            all_line_ids.extend(q.get('product_line_ids', []))

        quotation_products = []
        if all_line_ids:
            quotation_products = self.env['product.quotation.line'].search_read(
                [('id', 'in', all_line_ids)],
                ['id', 'name', 'subtotal', 'display_type'],
            )

        return {
            'products': products,
            'quotations': quotations,
            'quotation_products': quotation_products,
        }

    @api.model
    def get_board_update_hash(self, record_id):
        """Endpoint ligero para polling: retorna un hash basado en write_dates y counts."""
        if not record_id:
            return {'hash': ''}

        self.env.cr.execute("""
            SELECT
                COALESCE(COUNT(*), 0) AS product_count,
                COALESCE(MAX(write_date)::text, '') AS product_max_write,
                (SELECT COALESCE(COUNT(*), 0) FROM quotation_quotation WHERE request_quotation_id = %s) AS quotation_count,
                (SELECT COALESCE(MAX(write_date)::text, '') FROM quotation_quotation WHERE request_quotation_id = %s) AS quotation_max_write,
                (SELECT COALESCE(COUNT(*), 0) FROM product_quotation_line WHERE quotation_id IN
                    (SELECT id FROM quotation_quotation WHERE request_quotation_id = %s)) AS line_count,
                (SELECT COALESCE(MAX(write_date)::text, '') FROM product_quotation_line WHERE quotation_id IN
                    (SELECT id FROM quotation_quotation WHERE request_quotation_id = %s)) AS line_max_write
            FROM request_product_quotation_line
            WHERE request_quotation_id = %s
        """, [record_id, record_id, record_id, record_id, record_id])

        row = self.env.cr.dictfetchone()
        hash_str = f"{row['product_count']}:{row['product_max_write']}:{row['quotation_count']}:{row['quotation_max_write']}:{row['line_count']}:{row['line_max_write']}"
        return {'hash': hash_str}

    @api.model
    def get_product_wizard_view_id(self):
        """Obtiene la vista form para asignar productos requeridos.
        Cada modelo que hereda puede sobrescribir el xml_id."""
        xml_id = self._get_product_wizard_xml_id()
        data = self.env['ir.model.data'].sudo().search_read(
            [
                ("module", "=", "purchase_management"),
                ("name", "=", xml_id),
            ],
            ["res_id"]
        )
        return data[0]['res_id'] if data else False

    def _get_product_wizard_xml_id(self):
        """Retorna el xml_id de la vista de productos. Sobrescribir en cada modelo."""
        return "view_request_quotation_form_add_product"

    @api.model
    def subscribe_to_product_updates(self, record_id):
        if not record_id:
            return False
        record = self.browse(record_id)
        if not record.exists():
            return False

        channel_name = record._get_product_channel_name()
        self.env['bus.bus']._sendone(channel_name, 'purchase_management.product/subscribe', {
            'quotation_id': record_id,
            'action': 'subscribe',
            'timestamp': fields.Datetime.now().isoformat()
        })
        return channel_name
