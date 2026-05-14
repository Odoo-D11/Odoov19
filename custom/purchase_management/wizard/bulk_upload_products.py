from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from ..utils.utils import _build_bulk_upload_template, _build_available_units_of_measurement, convert_first_letter_to_uppercase, _clean_special_chars, _clean_note_text
from markupsafe import Markup
import base64
import io
import re
import openpyxl


class PurchaseBulkUploadProductsWizard(models.TransientModel):
    _name = 'purchase.bulk.upload.products.wizard'
    _description = 'Wizard para carga masiva de productos desde Excel'
    _transient_max_count = 100
    _transient_max_hours = 24

    """MANY2ONE"""
    request_quotation_id = fields.Many2one(
        'request.quotation', string='Solicitud de Cotización', readonly=True)
    """BINARY"""
    file_data = fields.Binary(string='Archivo Excel')
    """CHAR"""
    file_name = fields.Char(string='Nombre del archivo')
    """HTML"""
    validation_html = fields.Html(
        string='Resultado de validación', readonly=True)
    """BOOLEAN"""
    show_instructions = fields.Boolean(
        string='Mostrar instrucciones', default=True, readonly=True)
    show_upload = fields.Boolean(
        string='Mostrar carga', default=False, readonly=True)
    show_validation = fields.Boolean(
        string='Mostrar validación', default=False, readonly=True)

    def action_download_template(self):
        """Descarga la plantilla Excel vacía con dropdown de unidades de medida"""
        # Obtener las unidades de medida disponibles
        uom_list = self.env['warehouse.uom'].sudo().search([]).mapped('name')
        file_content = _build_bulk_upload_template(uom_list)
        file_name = 'Plantilla_Carga_Productos.xlsx'
        attachment = self.env['ir.attachment'].sudo().create({
            'name': file_name,
            'datas': base64.b64encode(file_content),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'type': 'binary',
            'public': True,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def action_download_uom(self):
        """Descarga la lista de unidades de medida"""
        file_content = _build_available_units_of_measurement(self)
        file_name = 'Lista_Unidades_Medida.xlsx'
        attachment = self.env['ir.attachment'].sudo().create({
            'name': file_name,
            'datas': base64.b64encode(file_content),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'type': 'binary',
            'public': True,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def action_validate_file(self):
        self.ensure_one()
        if not self.file_data:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Debe cargar un archivo Excel para continuar.'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        try:
            products = self._analyze_excel()
            errors, warnings = self._validate_data(products)
            if errors:
                self.validation_html = self._generate_error_html(
                    errors, len(products))
            else:
                self.validation_html = self._generate_success_html(
                    len(products), warnings)
            self.show_upload = False
            self.show_validation = True
            return {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'view_mode': 'form',
                'res_id': self.id,
                'target': 'new',
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error al procesar el archivo'),
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_next_to_upload(self):
        self.ensure_one()
        self.show_instructions = False
        self.show_upload = True
        self.show_validation = False
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_back_to_instructions(self):
        self.ensure_one()
        self.show_instructions = True
        self.show_upload = False
        self.show_validation = False
        self.validation_html = False
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_back_to_upload(self):
        self.ensure_one()
        self.show_instructions = False
        self.show_upload = True
        self.show_validation = False
        self.validation_html = False
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def _get_parent_record(self):
        """Retorna el registro padre (request.quotation)"""
        if self.request_quotation_id:
            return self.request_quotation_id
        raise UserError(_('No se encontró la solicitud asociada a esta carga masiva.'))

    def _get_fk_field(self):
        return 'request_quotation_id'

    def action_process_file(self):
        """Crea los registros"""
        self.ensure_one()
        try:
            # Analizamos el archivo Excel
            products = self._analyze_excel()
            errors, warnings = self._validate_data(products)
            if errors:
                raise UserError(
                    _('El archivo contiene errores. Por favor corrija y vuelva a intentar.'))
            parent = self._get_parent_record()
            if parent.state != 'draft':
                raise UserError(
                    _('La solicitud no está en estado borrador.'))
            # Crear los registros (request.product.quotation.line)
            self._create_product_lines(products)
            parent.sudo().message_post(
                body=Markup(
                    f"<span>Se han cargado <span style='color: #017e84;'>{len(products)} productos</span> "
                    f"mediante un Excel.</span>"
                )
            )
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Carga exitosa'),
                    'message': _('Se han cargado %s productos correctamente.') % len(products),
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.act_window_close'}
                }
            }
        except Exception as e:
            raise UserError(_('Error al procesar el archivo: %s') % str(e))

    def _analyze_excel(self):
        self.ensure_one()
        file_data = base64.b64decode(self.file_data)
        file_obj = io.BytesIO(file_data)
        try:
            workbook = openpyxl.load_workbook(file_obj, data_only=True)
            sheet = workbook.active
        except Exception as e:
            raise UserError(
                _('Error al leer el archivo Excel. Asegúrese de que sea un archivo .xlsx válido.'))
        # Validamos los encabezados
        expected_headers = ['Nombre', 'Especificación',
                            'Cantidad', 'Unidad de Medida']
        actual_headers = [cell.value for cell in sheet[1]][:4]
        if actual_headers != expected_headers:
            raise UserError(
                _('El archivo Excel no tiene los encabezados correctos.\n\n'
                  'Esperados: %s\n'
                  'Encontrados: %s\n\n'
                  'Por favor descargue la plantilla correcta y complete la información.')
                % (', '.join(expected_headers), ', '.join([str(h) for h in actual_headers]))
            )
        products = []
        # Leemos los valores desde la fila 2
        for row_num, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            # Si la fila está vacía, continuamos
            if not any(row):
                continue
            # Buscamos los valores (A: Nombre, B: Especificación, C: Cantidad, D: UdM)
            name = row[0] if len(row) > 0 else None
            specification = row[1] if len(row) > 1 else None
            qty = row[2] if len(row) > 2 else None
            uom = row[3] if len(row) > 3 else None
            products.append({
                'row_num': row_num,
                'name': name,
                'specification': specification,
                'qty': qty,
                'uom': uom,
            })
        if not products:
            raise UserError(
                _('El archivo Excel no contiene productos. Por favor agregue al menos un producto.'))
        return products

    def _validate_data(self, products):
        """Valida los datos del excel"""
        self.ensure_one()
        errors = []
        warnings = []
        for product in products:
            row_errors = self._validate_required_fields(product)
            errors.extend(row_errors)
        # Si hay errores de campos vacíos, no continua con otras validaciones
        if errors:
            return errors, warnings
        # Limpia los caracteres especiales del nombre
        for product in products:
            original_name = product['name']
            product['name'] = _clean_special_chars(str(original_name))
            if original_name != product['name']:
                warnings.append(
                    Markup("<b class='text-primary'>Fila %s:</b> Se limpiaron caracteres especiales en <b class='text-primary'>%s</b>") % (
                        product['row_num'], original_name.title())
                )
        # Solo permite tener productos con 25 caracteres (No cuenta espacios)
        for product in products:
            name_without_spaces = product['name'].replace(' ', '')
            if len(name_without_spaces) > 25:
                errors.append(
                    Markup("El nombre del producto en la <b class='text-primary'>Fila %s</b> excede los 25 caracteres permitidos (tiene %s caracteres sin contar espacios)") % (
                        product['row_num'], len(name_without_spaces))
                )
        # Busca los duplicados con especificaciones iguales
        excel_duplicates, db_duplicates = self._check_duplicates(products)
        # Si encuentra duplicados del Excel con misma especificación
        if excel_duplicates:
            for dup_name in excel_duplicates:
                errors.append(
                    Markup("El producto <b class='text-primary'>%s</b> está duplicado en el archivo con la misma especificación. Los productos duplicados <b class='text-primary'>deben tener especificaciones diferentes.</b>") % (
                        dup_name.title())
                )
        # Si encuentra duplicados en la solicitud con misma especificación
        if db_duplicates:
            for dup_name in db_duplicates:
                errors.append(
                    Markup("El producto <b class='text-primary'>%s</b> ya existe en la solicitud con la misma especificación. Los productos duplicados <b class='text-primary'>deben tener especificaciones diferentes.</b>") % (
                        dup_name.title()))

        # Unidad de Medida
        for product in products:
            is_valid, uom_id = self._validate_uom(product['uom'])
            if not is_valid:
                errors.append(
                    Markup("<b class='text-primary'>Fila %s:</b> La unidad de medida '%s' no existe</b>") % (
                        product['row_num'], product['uom'])
                )
            else:
                product['uom_id'] = uom_id
        # Cantidades
        for product in products:
            try:
                qty = float(product['qty'])
                if qty <= 0:
                    errors.append(
                        Markup("<b class='text-primary'>Fila %s:<b/> La cantidad debe ser mayor a 0") % (
                            product['row_num'])
                    )
                product['qty'] = qty
            except (ValueError, TypeError):
                errors.append(
                    Markup("<b class='text-primary'>Fila %s:</b> La cantidad %s no es un número válido") % (
                        product['row_num'], product['qty'])
                )
        return errors, warnings

    def _validate_required_fields(self, product):
        """Valida que todos los campos requeridos estén completos"""
        errors = []
        row_num = product['row_num']
        if not product.get('name') or str(product['name']).strip() == '':
            errors.append(f"Fila {row_num}: Falta nombre de producto")
        if not product.get('specification') or str(product['specification']).strip() == '':
            errors.append(f"Fila {row_num}: Falta especificación")
        if product.get('qty') is None or str(product['qty']).strip() == '':
            errors.append(f"Fila {row_num}: Falta cantidad")
        if not product.get('uom') or str(product['uom']).strip() == '':
            errors.append(f"Fila {row_num}: Falta unidad de medida")
        return errors

    def _check_duplicates(self, products):
        """Busca los duplicados con especificaciones iguales tanto del Excel como en request.product.quotation.line"""
        excel_duplicates = []
        db_duplicates = []

        # Crear lista de pares (nombre, especificación) del Excel
        excel_pairs = []
        for p in products:
            if p.get('name'):
                name = p['name'].strip().lower()
                spec = p.get('specification', '').strip().lower()
                excel_pairs.append((name, spec))

        # Buscar duplicados en el Excel (mismo nombre + misma especificación)
        seen_excel = set()
        for name, spec in excel_pairs:
            pair = (name, spec)
            if pair in seen_excel and name not in excel_duplicates:
                excel_duplicates.append(name)
            seen_excel.add(pair)

        # Obtener pares existentes en la solicitud usando secuencia
        parent = self._get_parent_record()
        sorted_lines = list(
            parent.product_line_ids.sorted('sequence'))
        existing_pairs = set()

        i = 0
        while i < len(sorted_lines):
            line = sorted_lines[i]
            if line.display_type != 'line_note' and line.name:
                prod_name = line.name.strip().lower()
                spec = ''
                # Buscar la nota que sigue inmediatamente
                if i + 1 < len(sorted_lines):
                    next_line = sorted_lines[i + 1]
                    if next_line.display_type == 'line_note' and next_line.product_name == line.name:
                        spec = (next_line.name or '').strip().lower()
                        i += 1  # Saltar la nota procesada
                existing_pairs.add((prod_name, spec))
            i += 1

        # Verificar si algún producto del Excel ya existe con la misma especificación
        for name, spec in excel_pairs:
            if (name, spec) in existing_pairs and name not in db_duplicates:
                db_duplicates.append(name)

        return excel_duplicates, db_duplicates

    def _validate_uom(self, uom_name):
        """Valida que la UdM exista en warehouse.uom"""
        if not uom_name:
            return False, None
        uom = self.env['warehouse.uom'].search([
            ('name', '=ilike', str(uom_name).strip())
        ], limit=1)
        if not uom:
            return False, None
        return True, uom.id

    def _create_product_lines(self, products):
        """Crea los registros de productos y especificaciones"""
        self.ensure_one()
        ProductLine = self.env['request.product.quotation.line']
        fk_field = self._get_fk_field()
        parent = self._get_parent_record()
        for product in products:
            # Crear línea de producto
            ProductLine.sudo().create({
                fk_field: parent.id,
                'name': product['name'].title(),
                'qty': product['qty'],
                'uom_id': product['uom_id'],
                'display_type': False,
                'sequence': 9999,
            })
            # Crear línea de especificación (nota)
            ProductLine.sudo().create({
                fk_field: parent.id,
                'name': _clean_note_text(product['specification']),
                'product_name': product['name'].title(),
                'display_type': 'line_note',
                'sequence': 9999,
            })

    def _generate_error_html(self, errors, total_products):
        error_rows = ''
        for error in errors:
            error_rows += f'''
            <div class="d-flex align-items-baseline bg-white p-2 mb-2 rounded border">
                <div class="text-primary mr-2 me-2 text-center" style="min-width: 20px;">
                    <i class="fa fa-times-circle" style="font-size: 0.9rem;"></i>
                </div>
                <div class="flex-grow-1">
                    <span class="text-dark" style="font-size: 0.9rem; line-height: 1.5;">{error}</span>
                </div>
            </div>
            '''

        return Markup(f"""
            <div class="bg-white rounded shadow-sm border p-0 overflow-hidden">
                <div class="row no-gutters">
                    <div class="col-md-4 bg-primary text-white d-flex flex-column align-items-center justify-content-center p-4 text-center">
                        <div class="mb-3">
                            <i class="fa fa-exclamation-triangle fa-4x text-white"></i>
                        </div>
                        <h3 class="font-weight-bold m-0 text-white">ERROR</h3>

                        <p class="mb-0 mt-3 text-white" style="opacity: 0.9; font-size: 0.9rem;">
                            Hemos encontrado inconsistencias en los datos. El archivo no puede ser procesado hasta que se realicen las correcciones.
                        </p>
                    </div>

                    <div class="col-md-8 p-0">
                        <div class="px-4 py-3 border-bottom bg-white d-flex justify-content-between align-items-center">
                            <div>
                                <h5 class="text-dark font-weight-bold m-0">Detalle de validación</h5>
                                <small class="text-muted" style="font-size: 0.85rem;">
                                    Revise los registros listados a continuación.
                                </small>
                            </div>
                            <span class="badge badge-primary px-3 py-2" style="font-size: 0.9rem;">
                                {len(errors)} {'registro' if len(errors) == 1 else 'registros'}
                            </span>
                        </div>

                        <div class="bg-light" style="height: 280px; overflow-y: auto; border-bottom: 1px solid #dee2e6; padding: 16px 32px 16px 16px;">
                            {error_rows}
                        </div>

                        <div class="px-4 py-2 bg-white text-right text-end">
                            <small class="text-muted font-italic">
                                <i class="fa fa-info-circle text-primary mr-1 me-1"></i>
                                Edite el archivo Excel en su equipo y vuelva a cargarlo.
                            </small>
                        </div>
                    </div>
                </div>
            </div>
        """)

    def _generate_success_html(self, total_products, warnings):
        # Sin observaciones
        if not warnings:
            return Markup(f"""
                <div class="bg-white rounded shadow-sm border p-0 overflow-hidden">
                    <div class="row no-gutters align-items-stretch">
                        <div class="col-md-4 bg-primary text-white d-flex flex-column align-items-center justify-content-center p-4 text-center">
                            <div class="mb-3">
                                <i class="fa fa-check-circle fa-4x text-white"></i>
                            </div>
                            <h4 class="font-weight-bold text-white">¡Todo Listo!</h4>
                            <p class="small mb-0" style="opacity: 0.9;">
                                La información es correcta y está lista para ser cargada.
                            </p>
                        </div>

                        <div class="col-md-8 p-4">
                            <h5 class="text-dark text-uppercase font-weight-bold mb-4"
                                style="font-size: 12px; letter-spacing: 1px;">
                                Resumen de Importación
                            </h5>

                            <div class="row text-center mb-4">
                                <div class="col-6 border-right border-end">
                                    <h2 class="text-primary font-weight-bold m-0">{total_products}</h2>
                                    <small class="text-muted">Productos</small>
                                </div>
                                <div class="col-6">
                                    <h2 class="text-primary font-weight-bold m-0">
                                        <i class="fa fa-check"></i>
                                    </h2>
                                    <small class="text-muted">Unidades Medida</small>
                                </div>
                            </div>

                            <div class="d-flex align-items-center p-3 rounded" style="background-color: #f8f9fa;">
                                <i class="fa fa-arrow-right text-primary mr-3 me-3 fa-lg"></i>
                                <div>
                                    <span class="d-block text-dark font-weight-bold">Siguiente paso:</span>
                                    <span class="small text-muted">
                                        Haga clic en el botón "Guardar" para finalizar.
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            """)

        # Con observaciones
        warning_rows = ''
        for w in warnings:
            warning_rows += f"""
                <div class="d-flex align-items-baseline bg-white p-2 mb-2 rounded border w-100">
                    <div class="text-primary mr-2 me-2 text-center" style="min-width: 20px;">
                        <i class="fa fa-info-circle" style="font-size: 0.9rem;"></i>
                    </div>
                    <div class="flex-grow-1" style="min-width: 0;">
                        <span class="text-dark d-block text-break" style="font-size: 0.9rem; line-height: 1.4;">
                            {w}
                        </span>
                    </div>
                </div>
            """

        return Markup(f"""
            <div class="bg-white rounded shadow-sm border p-0 overflow-hidden">
                <div class="row no-gutters">
                    <div class="col-md-4 bg-primary text-white d-flex flex-column align-items-center justify-content-center p-4 text-center">
                        <div class="mb-3">
                            <i class="fa fa-check-circle fa-4x text-white"></i>
                        </div>
                        <h3 class="font-weight-bold m-0 text-white">¡Todo Listo!</h3>
                        <p class="mb-0 mt-3 text-white" style="opacity: 0.9; font-size: 0.9rem;">
                            Los datos son válidos. Se han aplicado algunas limpiezas automáticas.
                        </p>
                    </div>

                    <div class="col-md-8 p-0 d-flex flex-column">

                        <div class="p-3 border-bottom bg-white d-flex justify-content-between align-items-center">
                            <div>
                                <h5 class="text-dark font-weight-bold m-0">Observaciones</h5>
                                <small class="text-muted" style="font-size: 0.85rem;">
                                    Validaciones automáticas del sistema.
                                </small>
                            </div>
                            <span class="badge badge-primary px-3 py-2" style="font-size: 0.9rem;">
                                {len(warnings)} {'registro' if len(warnings) == 1 else 'registros'}
                            </span>
                        </div>

                        <div class="bg-light flex-grow-1"
                            style="max-height: 280px; overflow-y: auto;">
                            <div style="padding: 16px 32px 16px 16px;">
                                {warning_rows}
                            </div>
                        </div>

                        <div class="bg-white text-right text-end border-top mt-auto"
                             style="padding: 12px 32px 12px 16px;">
                            <small class="text-muted font-italic d-inline-block"
                                   style="font-size: 0.85rem;">
                                <i class="fa fa-info-circle text-primary mr-1 me-1"></i>
                                {total_products} Productos
                                <span class="mx-2">|</span>
                                <i class="fa fa-check-circle text-primary mr-1 me-1"></i>
                                UdM
                            </small>
                        </div>
                    </div>
                </div>
            </div>
        """)
