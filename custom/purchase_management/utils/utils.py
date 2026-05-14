# -*- coding: utf-8 -*-

from odoo.addons.utils.models.utils import (  # type: ignore
    format_html_to_sentence_case,
    convert_first_letter_to_uppercase,
    is_valid_url,
    _clean_name
)
from odoo.exceptions import UserError
from odoo import _
import io
import xlsxwriter
import base64
import random
import colorsys
import re


def _show_error_notification(self, message):
    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {'title': _('Error'), 'message': message, 'type': 'danger', 'sticky': False}
    }


def _clean_note_text(text):
    """
    Limpia texto de notas/especificaciones, removiendo HTML y normalizando espacios.
    """
    if not text:
        return text
    import html
    text = str(text)
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = text.replace('\t', ' ')
    text = text.replace('\r', '')
    text = text.replace('\xa0', ' ')
    text = re.sub(r'\n+', ', ', text)
    text = re.sub(r' +', ' ', text)
    text = re.sub(r',\s*,+', ',', text)
    parts = text.split(',')
    cleaned_parts = []
    for part in parts:
        part = part.strip()
        if part:
            formatted_part = part[:1].upper() + part[1:].lower()
            cleaned_parts.append(formatted_part)
    return ", ".join(cleaned_parts)


def _clean_special_chars(text):
    """
    Elimina caracteres especiales del nombre del producto y normaliza tildes,
    preservando la ñ/Ñ.

    Transformaciones:
    - Tildes/acentos se convierten a letra base: café -> cafe
    - La ñ/Ñ se preserva: niño -> niño, español -> español
    - Caracteres especiales (#, /, !, $, &, @, *, %) se eliminan
    - Espacios y comillas dobles se preservan

    Ej.
    - "Café especial #1" -> "Cafe especial 1"
    - "Niño & Niña" -> "Niño  Niña"
    - "Producto común" -> "Producto comun"
    """
    if not text:
        return text
    import unicodedata
    text = str(text)
    # Preservar ñ/Ñ con placeholders únicos
    text = text.replace('ñ', '##ENIE_MIN##').replace('Ñ', '##ENIE_MAY##')
    # Normalizar y quitar acentos
    normalized = unicodedata.normalize('NFD', text)
    without_accents = ''.join(
        char for char in normalized
        if unicodedata.category(char) != 'Mn'
    )
    # Restaurar ñ/Ñ
    without_accents = without_accents.replace(
        '##ENIE_MIN##', 'ñ').replace('##ENIE_MAY##', 'Ñ')
    # Eliminar caracteres especiales, mantener letras (incluyendo ñ), números, espacios y comillas
    cleaned = re.sub(r'[^a-zA-ZñÑ0-9" ]', '', without_accents)
    return cleaned.strip()


def _build_excel_file_supplier(self, selected_product_ids=None):
    """
    Genera el archivo Excel para enviar a proveedores.

    Args:
        self: request.quotation (Id)
        selected_product_ids: lista de IDs de productos a incluir. Si es None, incluye todos.
    """
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})

    # =========================
    # PALETA
    # =========================
    corp_dark = "#02143f"
    line_grey = "#A6A6A6"
    white = "#FFFFFF"
    soft_yellow = "#FFFCE0"
    soft_grey = "#E6E6E6"

    # =========================
    # FORMATOS
    # =========================
    fmt_doc_title = workbook.add_format({
        "bold": True, "font_size": 16, "font_color": white,
        "bg_color": corp_dark, "align": "center", "valign": "vcenter",
    })

    fmt_doc_subtitle = workbook.add_format({
        "bold": True, "font_size": 10, "font_color": corp_dark,
        "align": "center", "valign": "vcenter",
        "bottom": 2, "bottom_color": corp_dark,
    })

    fmt_section = workbook.add_format({
        "bold": True, "font_size": 12, "font_color": corp_dark,
        "bottom": 2, "bottom_color": corp_dark,
        "align": "left", "valign": "vcenter",
    })

    fmt_section_spacer = workbook.add_format({
        "bold": True, "font_size": 12, "font_color": corp_dark,
        "align": "left", "valign": "vcenter",
    })

    fmt_label = workbook.add_format({
        "bold": True, "font_color": white, "bg_color": corp_dark,
        "border": 1, "border_color": line_grey,
        "align": "left", "valign": "vcenter", "indent": 1,
    })

    fmt_label_center = workbook.add_format({
        "bold": True, "font_color": white, "bg_color": corp_dark,
        "border": 1, "border_color": line_grey,
        "align": "center", "valign": "vcenter",
    })

    # Inputs centrados
    fmt_input_center = workbook.add_format({
        "bg_color": white,
        "border": 1, "border_color": line_grey,
        "align": "center", "valign": "vcenter",
        "text_wrap": True,
        "font_color": "#000000",
    })

    fmt_tbl_header = workbook.add_format({
        "bold": True, "font_color": white, "bg_color": corp_dark,
        "border": 1, "border_color": corp_dark,
        "align": "center", "valign": "vcenter",
    })

    # Producto
    fmt_txt = workbook.add_format({
        "border": 1, "border_color": "#000000",
        "align": "left", "valign": "vcenter", "text_wrap": True,
        "font_color": "#000000",
        "indent": 1,
    })

    fmt_center_black = workbook.add_format({
        "border": 1, "border_color": "#000000",
        "align": "center", "valign": "vcenter",
        "font_color": "#000000",
    })

    # Formato para especificaciones (notas)
    fmt_specification = workbook.add_format({
        "border": 1, "border_color": "#000000",
        "bg_color": "#f5f5f5",
        "align": "left",
        "valign": "vcenter",
        "text_wrap": True,
        "font_color": "#000000",
        "italic": True,
        "indent": 1,
    })

    money_format = "#,##0.00"

    # Precio Unitario
    fmt_money_edit = workbook.add_format({
        "border": 1, "border_color": "#000000",
        "bg_color": soft_yellow,
        "num_format": money_format,
        "align": "center", "valign": "vcenter",
        "font_color": "#000000",
    })

    # Subtotal
    fmt_subtotal = workbook.add_format({
        "border": 1, "border_color": "#000000",
        "bg_color": soft_grey,
        "num_format": money_format,
        "align": "right", "valign": "vcenter",
        "font_color": "#000000",
        "bold": True,
        "indent": 1,
    })

    # Total
    fmt_total_value = workbook.add_format({
        "border": 1, "border_color": "#000000",
        "bg_color": soft_grey,
        "num_format": money_format,
        "align": "right", "valign": "vcenter",
        "font_color": "#000000",
        "bold": True,
        "indent": 1,
    })

    fmt_na_cell = workbook.add_format({
        "bg_color": soft_grey,
        "font_color": "#000000",
        "border": 1, "border_color": line_grey,
        "align": "center", "valign": "vcenter",
        "bold": True,
    })

    fmt_obs_label = workbook.add_format({
        "bold": True, "font_color": white, "bg_color": corp_dark,
        "align": "center", "valign": "vcenter",
        "bottom": 1, "bottom_color": line_grey,
    })

    fmt_obs_input = workbook.add_format({
        "font_color": "#000000",
        "align": "center", "valign": "vcenter",
        "bottom": 1, "bottom_color": line_grey,
        "text_wrap": True,
    })

    # =========================
    # HOJA
    # =========================
    ws = workbook.add_worksheet("Formato")
    ws.hide_gridlines(2)

    ws.set_tab_color("#FFFFFF")

    # Columnas
    ws.set_column("A:A", 2.73)
    ws.set_column("B:B", 14.73)
    ws.set_column("C:D", 13)
    ws.set_column("E:E", 16.73)
    ws.set_column("F:G", 13)
    ws.set_column("H:H", 12.73)
    ws.set_column("I:I", 13)
    ws.set_column("J:J", 14.73)
    ws.set_column("K:L", 13)

    def section_title(row, title):
        ws.set_row(row, 15.5)
        ws.merge_range(row, 1, row, 11, title, fmt_section)
        ws.set_row(row + 1, 15.5, fmt_section_spacer)
        return row + 2

    # =========================
    # ENCABEZADO
    # =========================
    r = 0
    ws.set_row(r, 30)
    ws.merge_range(
        r, 1, r, 11, "FORMATO DE COTIZACIÓN / OFERTA", fmt_doc_title)
    r += 1

    ws.set_row(r, 18)
    ws.merge_range(
        r, 1, r, 11, "Documento para diligenciamiento del proveedor", fmt_doc_subtitle)
    r += 2

    # =========================
    # PROVEEDOR
    # =========================
    r = section_title(r, "PROVEEDOR")

    ws.set_row(r, 20)
    ws.merge_range(r, 1, r, 3, "Nombre", fmt_label)
    ws.merge_range(r, 4, r, 11, "", fmt_input_center)
    r += 1

    ws.set_row(r, 20)
    ws.merge_range(r, 1, r, 3, "NIT", fmt_label)
    ws.merge_range(r, 4, r, 6, "", fmt_input_center)
    ws.merge_range(r, 7, r, 8, "Telefono", fmt_label)
    ws.merge_range(r, 9, r, 11, "", fmt_input_center)
    r += 2

    # =========================
    # INFORMACIÓN DE LA OFERTA
    # =========================
    r = section_title(r, "INFORMACIÓN DE LA OFERTA")

    ws.set_row(r, 20)
    ws.merge_range(r, 1, r, 3, "Fecha de Vigencia", fmt_label)
    ws.merge_range(r, 4, r, 6, "", fmt_input_center)

    ws.merge_range(r, 7, r, 8, "Moneda", fmt_label)
    ws.write(r, 9, "", fmt_input_center)         # J (Moneda)
    ws.write(r, 10, "TRM", fmt_label_center)     # K
    ws.write(r, 11, "N/A", fmt_input_center)     # L (TRM)

    currency_row = r
    currency_cell_abs = f"$J${currency_row + 1}"
    trm_cell_abs = f"$L${currency_row + 1}"

    ws.data_validation(
        r, 9, r, 9, {"validate": "list", "source": ["COP", "USD"]})

    ws.conditional_format(r, 11, r, 11, {
        "type": "formula",
        "criteria": f'={trm_cell_abs}="N/A"',
        "format": fmt_na_cell,
    })

    ws.data_validation(r, 11, r, 11, {
        "validate": "custom",
        "value": (
            f'=IF(OR({currency_cell_abs}="",{currency_cell_abs}="COP"),'
            f'{trm_cell_abs}="N/A",'
            f'AND(ISNUMBER({trm_cell_abs}),{trm_cell_abs}>0)'
            f')'
        ),
        "error_type": "stop",
        "error_title": "TRM inválida",
        "error_message": 'Valor inválido para TRM. Si "Moneda" es "COP" (o vacío), debe ser "N/A". Si es "USD", debe ser numérico y > 0.',
    })
    r += 1

    # ---- Lugar de Entrega | Fecha de Entrega
    label = ''
    if hasattr(self, 'additional_info_ids') and self.additional_info_ids:
        info_record = self.additional_info_ids[:1]
        label = dict(info_record._fields['location_delivery'].selection).get(
            info_record.location_delivery, '')
    ws.set_row(r, 20)
    ws.merge_range(r, 1, r, 3, "Lugar de Entrega", fmt_label)
    ws.merge_range(r, 4, r, 6, label, fmt_input_center)

    ws.merge_range(r, 7, r, 8, "Fecha de Entrega", fmt_label)
    ws.merge_range(r, 9, r, 11, "", fmt_input_center)
    r += 1

    # ---- ¿Incluye Flete? (E) + Precio Est. (F/G)
    ws.set_row(r, 20)
    ws.merge_range(r, 1, r, 3, "¿Incluye Flete?", fmt_label)

    ws.write(r, 4, "", fmt_input_center)  # E
    ws.data_validation(
        r, 4, r, 4, {"validate": "list", "source": ["Sí", "No"]})

    ws.write(r, 5, "Precio Est.", fmt_label_center)  # F
    ws.write(r, 6, "N/A", fmt_input_center)          # G

    flete_row = r
    flete_cell_abs = f"$E${flete_row + 1}"
    price_est_cell_abs = f"$G${flete_row + 1}"

    ws.conditional_format(r, 6, r, 6, {
        "type": "formula",
        "criteria": f'={price_est_cell_abs}="N/A"',
        "format": fmt_na_cell,
    })

    # Precio Est.: No/vacío -> N/A; Sí -> numérico > 0 (NO permite vacío)
    ws.data_validation(r, 6, r, 6, {
        "validate": "custom",
        "value": (
            f'=IF(OR({flete_cell_abs}="",{flete_cell_abs}="No"),'
            f'{price_est_cell_abs}="N/A",'
            f'AND(ISNUMBER({price_est_cell_abs}),{price_est_cell_abs}>0)'
            f')'
        ),
        "error_type": "stop",
        "error_title": "Precio Est. inválido",
        "error_message": 'Si "¿Incluye Flete?" es "No" (o vacío), debe ser "N/A". Si es "Sí", debe ser numérico y > 0.',
    })

    r += 3

    # =========================
    # PRODUCTOS SOLICITADOS
    # =========================
    r = section_title(r, "PRODUCTOS SOLICITADOS")

    ws.set_row(r, 20)
    ws.merge_range(r, 1, r, 2, "Nombre", fmt_tbl_header)               # B–C
    ws.merge_range(r, 3, r, 4, "Especificación", fmt_tbl_header)       # D–E
    ws.write(r, 5, "Cantidad", fmt_tbl_header)                         # F
    ws.write(r, 6, "UdM", fmt_tbl_header)                              # G
    ws.merge_range(r, 7, r, 9, "Precio Unitario / Sin Iva",
                   fmt_tbl_header)      # H–J
    ws.merge_range(r, 10, r, 11, "Subtotal", fmt_tbl_header)           # K–L
    r += 1

    first_line_r = r
    line_count = 0
    product_rows = []

    # Ordena las líneas por secuencia para mostrar productos y especificaciones en orden
    sorted_lines = list(self.product_line_ids.sorted('sequence'))

    # Crear lista de pares (producto, nota) usando secuencia
    product_note_pairs = []
    i = 0
    while i < len(sorted_lines):
        line = sorted_lines[i]
        if line.display_type != 'line_note':
            # Es un producto, buscar su nota (debe ser la siguiente línea)
            note_line = None
            if i + 1 < len(sorted_lines):
                next_line = sorted_lines[i + 1]
                if next_line.display_type == 'line_note' and next_line.product_name == line.name:
                    note_line = next_line
                    i += 1  # Saltar la nota procesada
            product_note_pairs.append((line, note_line))
        i += 1

    # Filtrar productos si se especificaron IDs seleccionados
    if selected_product_ids is not None:
        product_note_pairs = [
            (p, n) for p, n in product_note_pairs if p.id in selected_product_ids]

    # Validar que cada producto tenga especificación
    products_without_spec = [p.name for p,
                             n in product_note_pairs if n is None]

    if products_without_spec:
        raise UserError(
            _("Los siguientes productos no tienen especificación. Es obligatorio:\n- %s") %
            "\n- ".join(products_without_spec)
        )

    for product, note in product_note_pairs:
        line_count += 1
        product_rows.append(r)  # Guardar fila del producto
        ws.set_row(r, 36)

        p_name = product.name or ""
        qty = float(product.qty or 0.0)
        uom = product.uom_id.name if product.uom_id else ""

        # Obtener la especificación del producto
        spec_text = (note.name or "").strip() if note else ""

        # B-C: Nombre
        ws.merge_range(r, 1, r, 2, p_name, fmt_txt)
        # D-E: Especificación
        ws.merge_range(r, 3, r, 4, spec_text, fmt_specification)
        # F: Cantidad
        ws.write_number(r, 5, qty, fmt_center_black)
        ws.write(r, 6, uom, fmt_center_black)                          # G: UdM

        # H-J: Precio Unitario
        ws.merge_range(r, 7, r, 9, "", fmt_money_edit)

        # K-L: Subtotal
        ws.merge_range(r, 10, r, 11, "", fmt_subtotal)
        excel_row = r + 1
        subtotal_formula = (
            f'=F{excel_row}*H{excel_row}*'
            f'IF({currency_cell_abs}="USD",IF(ISNUMBER({trm_cell_abs}),{trm_cell_abs},0),1)'
        )
        ws.write_formula(r, 10, subtotal_formula, fmt_subtotal, 0)

        r += 1

    # Calcular fórmula del total solo con filas de productos
    if product_rows:
        # Sumar solo las celdas K de las filas de productos
        sum_parts = [f"K{row + 1}" for row in product_rows]
        grand_total_formula = f"={'+'.join(sum_parts)}"
    else:
        grand_total_formula = "=0"

    # =========================
    # OBSERVACIONES + TOTAL
    # =========================
    obs_top = r + 2
    obs_bottom = obs_top + 1

    ws.set_row(obs_top, 20)
    ws.set_row(obs_bottom, 20)

    ws.merge_range(obs_top, 1, obs_bottom, 2,
                   "Observaciones", fmt_obs_label)  # B–C
    ws.merge_range(obs_top, 3, obs_bottom, 8, "",
                   fmt_obs_input)              # D–I

    ws.write(obs_bottom, 10, "Total",
             fmt_tbl_header)                         # K
    ws.write_formula(obs_bottom, 11, grand_total_formula,
                     fmt_total_value, 0)  # L

    workbook.close()
    output.seek(0)
    return output.getvalue()


def get_distinct_colors(num_colors):
    """ 
    Genera una lista de strings con formato 'R,G,B' (Se usa al momento de mostrar el cuadro comparativo) 
    y permite que cada proveedor tenga un color distinto.
    """
    colors = []
    if num_colors < 1:
        return colors

    saturation = 0.75
    lightness = 0.6
    start_hue = random.random()
    hue_step = 1.0 / num_colors

    for i in range(num_colors):
        h = (start_hue + (i * hue_step)) % 1.0
        r_float, g_float, b_float = colorsys.hls_to_rgb(
            h, lightness, saturation)
        r, g, b = int(r_float * 255), int(g_float * 255), int(b_float * 255)

        colors.append(f"{r},{g},{b}")

    return colors


def _build_bulk_upload_template(uom_list=None):
    """
    Genera la plantilla Excel para carga masiva de productos (request.quotation).

    Args:
        uom_list: Lista de nombres de unidades de medida para el dropdown.
                  Si es None o vacía, no se agrega validación de lista.
    """
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    corp_dark = "#02143f"
    white = "#FFFFFF"
    line_grey = "#A6A6A6"

    # =========================
    # FORMATO
    # =========================
    fmt_header = workbook.add_format({
        "bold": True,
        "font_color": white,
        "bg_color": corp_dark,
        "border": 1,
        "border_color": corp_dark,
        "align": "center",
        "valign": "vcenter",
    })

    fmt_text = workbook.add_format({
        "border": 1,
        "border_color": line_grey,
        "align": "left",
        "valign": "vcenter",
        "text_wrap": True,
    })

    # =========================
    # CREAR LA HOJA PRINCIPAL
    # =========================
    worksheet = workbook.add_worksheet("Productos")

    # ===================
    # ANCHO DE LAS COLUMNAS (APROX.)
    # ===================
    worksheet.set_column("A:A", 30)  # Nombre
    worksheet.set_column("B:B", 50)  # Especificación
    worksheet.set_column("C:C", 15)  # Cantidad
    worksheet.set_column("D:D", 20)  # Unidad de Medida

    # =========================
    # ENCABEZADOS
    # =========================
    headers = ["Nombre", "Especificación", "Cantidad", "Unidad de Medida"]

    for col, header in enumerate(headers):
        worksheet.write(0, col, header, fmt_header)

    # =========================
    # CONFIGURAR DROPDOWN DE UNIDADES DE MEDIDA
    # =========================
    if uom_list and len(uom_list) > 0:
        # Crear hoja oculta para almacenar las unidades de medida
        uom_sheet = workbook.add_worksheet("_UdM_Lista")
        uom_sheet.hide()

        # Escribir las unidades de medida en la hoja oculta
        for row_idx, uom_name in enumerate(uom_list):
            uom_sheet.write(row_idx, 0, uom_name)

        # Crear nombre de rango para la lista de UdM
        uom_range = f"'_UdM_Lista'!$A$1:$A${len(uom_list)}"

        # Aplicar validación de lista a la columna D (Unidad de Medida)
        # desde la fila 2 hasta la fila 1000 (suficiente para uso normal)
        worksheet.data_validation(1, 3, 1000, 3, {
            'validate': 'list',
            'source': uom_range,
            'input_title': 'Unidad de Medida',
            'input_message': 'Seleccione una unidad de medida de la lista desplegable.',
            'error_title': 'Unidad no válida',
            'error_message': 'Por favor seleccione una unidad de medida de la lista disponible.',
            'error_type': 'warning',
        })

    # =========================
    # FILA DE EJEMPLO
    # =========================
    worksheet.write(1, 0, "Ejemplo: Cable HDMI", fmt_text)
    worksheet.write(
        1, 1, "Cable HDMI 2.0 de alta velocidad, 4K@60Hz, longitud 2 metros", fmt_text)
    worksheet.write(1, 2, "10", fmt_text)
    # En la fila de ejemplo, usar la primera UdM de la lista si existe
    example_uom = uom_list[0] if uom_list and len(uom_list) > 0 else "Unidad"
    worksheet.write(1, 3, example_uom, fmt_text)

    workbook.close()
    return output.getvalue()


def _build_available_units_of_measurement(self):
    """Genera la plantilla Excel para ver las unidades de 
    medida disponibles en el sistema (warehouse.uom)"""
    udm = self.env['warehouse.uom'].sudo().search([]).mapped('name')
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    corp_dark = "#02143f"
    white = "#FFFFFF"
    line_grey = "#A6A6A6"

    # =========================
    # FORMATO
    # =========================
    fmt_header = workbook.add_format({
        "bold": True,
        "font_color": white,
        "bg_color": corp_dark,
        "border": 1,
        "border_color": corp_dark,
        "align": "center",
        "valign": "vcenter",
    })

    fmt_text = workbook.add_format({
        "border": 1,
        "border_color": line_grey,
        "align": "left",
        "valign": "vcenter",
        "text_wrap": True,
    })

    # =========================
    # CREAR LA HOJA
    # =========================
    worksheet = workbook.add_worksheet("Unidades de Medida")

    # ===================
    # ANHCO DE LAS COLUMNAS (APROX.)
    # ===================

    worksheet.set_column("A:A", 30)  # Nombre

    # =========================
    # ENCABEZADOS
    # =========================

    headers = ["Nombre"]

    for col, header in enumerate(headers):
        worksheet.write(0, col, header, fmt_header)

    for row, u in enumerate(udm):
        worksheet.write(row + 1, 0, u, fmt_text)

    workbook.close()
    return output.getvalue()


def _build_bulk_import_request_template(type_list=None, project_list=None, uom_list=None):
    """
    Plantilla Excel para el wizard Nueva SDC (2 hojas):
      - Hoja "Solicitud": Tipo, Proyecto, Asunto, Fecha Límite, Motivo
      - Hoja "Productos": Nombre, Especificación, Cantidad, Unidad de Medida
    """
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    corp_dark = "#02143f"
    white = "#FFFFFF"
    line_grey = "#A6A6A6"

    fmt_header = workbook.add_format({
        "bold": True, "font_color": white, "bg_color": corp_dark,
        "border": 1, "border_color": corp_dark,
        "align": "center", "valign": "vcenter",
    })
    fmt_text = workbook.add_format({
        "border": 1, "border_color": line_grey,
        "align": "left", "valign": "vcenter", "text_wrap": True,
    })
    fmt_date = workbook.add_format({
        "border": 1, "border_color": line_grey,
        "align": "left", "valign": "vcenter", "num_format": "yyyy-mm-dd",
    })

    ws_solicitud = workbook.add_worksheet("Solicitud")
    ws_productos = workbook.add_worksheet("Productos")

    # Hojas ocultas para dropdowns
    if type_list:
        ts = workbook.add_worksheet("_Tipos_Lista")
        ts.hide()
        for i, n in enumerate(type_list):
            ts.write(i, 0, n)
        type_range = f"'_Tipos_Lista'!$A$1:$A${len(type_list)}"

    if project_list:
        ps = workbook.add_worksheet("_Proyectos_Lista")
        ps.hide()
        for i, n in enumerate(project_list):
            ps.write(i, 0, n)
        project_range = f"'_Proyectos_Lista'!$A$1:$A${len(project_list)}"

    if uom_list:
        us = workbook.add_worksheet("_UdM_Lista_Import")
        us.hide()
        for i, n in enumerate(uom_list):
            us.write(i, 0, n)
        uom_range = f"'_UdM_Lista_Import'!$A$1:$A${len(uom_list)}"

    # Hoja 1: Solicitud
    ws_solicitud.set_column("A:A", 25)
    ws_solicitud.set_column("B:B", 30)
    ws_solicitud.set_column("C:C", 40)
    ws_solicitud.set_column("D:D", 18)
    ws_solicitud.set_column("E:E", 55)
    for col, h in enumerate(["Tipo de Solicitud", "Proyecto", "Asunto", "Fecha Límite", "Motivo"]):
        ws_solicitud.write(0, col, h, fmt_header)

    ex_type = type_list[0] if type_list else "Productos"
    ex_project = project_list[0] if project_list else "Administrativo - 30"
    ws_solicitud.write(1, 0, ex_type,    fmt_text)
    ws_solicitud.write(1, 1, ex_project, fmt_text)
    ws_solicitud.write(1, 2, "Suministro de material de oficina", fmt_text)
    ws_solicitud.write(1, 3, "2026-12-31", fmt_date)
    ws_solicitud.write(
        1, 4, "Se requieren suministros para el área administrativa.", fmt_text)

    if type_list:
        ws_solicitud.data_validation(1, 0, 1, 0, {
            'validate': 'list', 'source': type_range,
            'error_title': 'Tipo no válido',
            'error_message': 'Seleccione un tipo de la lista.',
            'error_type': 'warning',
        })
    if project_list:
        ws_solicitud.data_validation(1, 1, 1, 1, {
            'validate': 'list', 'source': project_range,
            'error_title': 'Proyecto no válido',
            'error_message': 'Seleccione un proyecto de la lista.',
            'error_type': 'warning',
        })

    # Hoja 2: Productos
    ws_productos.set_column("A:A", 30)
    ws_productos.set_column("B:B", 55)
    ws_productos.set_column("C:C", 15)
    ws_productos.set_column("D:D", 22)
    for col, h in enumerate(["Nombre", "Especificación", "Cantidad", "Unidad de Medida"]):
        ws_productos.write(0, col, h, fmt_header)

    ws_productos.write(1, 0, "Computador Portátil", fmt_text)
    ws_productos.write(
        1, 1, "Procesador i7 12Gen, 16GB RAM, 512GB SSD, 14\" FHD, Win11 Pro", fmt_text)
    ws_productos.write(1, 2, "2", fmt_text)
    ex_uom = uom_list[0] if uom_list else "Unidad"
    ws_productos.write(1, 3, ex_uom, fmt_text)

    if uom_list:
        ws_productos.data_validation(1, 3, 1000, 3, {
            'validate': 'list', 'source': uom_range,
            'error_title': 'UdM no válida',
            'error_message': 'Seleccione una unidad de medida de la lista.',
            'error_type': 'warning',
        })

    workbook.close()
    return output.getvalue()
