# -*- coding: utf-8 -*-
import locale
from bs4 import BeautifulSoup
from odoo.addons.utils.models.utils import (  # type: ignore
    is_html_content_empty,
    format_html_to_sentence_case,
    convert_first_letter_to_uppercase,
    is_valid_url,
)

"""VALORACIÓN FINANCIERA"""


def edit_financial_values(html):
    """
    Extrae de la tabla los valores de descripción y porcentaje.

    :param html: Cadena de texto con el HTML.
    :return: Diccionario con las descripciones como claves y los porcentajes como valores.
    """
    soup = BeautifulSoup(html, 'html.parser')
    tbody = soup.find('tbody', id='financial-body')
    values = {}
    if tbody:
        for tr in tbody.find_all('tr'):
            cell_desc = tr.find('td', class_='description')
            cell_perc = tr.find('td', class_='percentage')
            if cell_desc and cell_perc:
                description = cell_desc.get_text(strip=True)
                percentage_text = cell_perc.get_text(strip=True)
                percentage = float(percentage_text.replace(
                    '%', '')) if percentage_text else 0.0
                # Filtrar las descripciones que no son porcentajes
                if description not in ["Utilidad Bruta", "EBITDA", "EBIT", "Utilidad Neta"]:
                    values[description] = percentage
    return values


def calculate_financial_data(income, cost, cost_values):
    """
    Realiza los cálculos financieros para generar los valores de costos y ganancias.

    :param income: Ingresos totales
    :param cost: Costo total
    :param cost_values: Diccionario con los valores de porcentaje de costos
    :return: Diccionario con los valores calculados
    """

    # Función para calcular costos según el porcentaje correspondiente
    def calculate_cost(cost_name, base_value):
        return base_value * (cost_values.get(cost_name, 0) / 100)

    # Cálculo de costos individuales
    financial_data = {
        "insurance_and_policies": calculate_cost('Seguro y pólizas', income),
        "overhead": calculate_cost('Overhead', cost),
        "unforeseen": calculate_cost('Imprevistos', cost),
        "commission": calculate_cost('Comisión', income),
        "legal": calculate_cost('Jurídico', income),
        "financing": calculate_cost('FINANCIACION', cost),
        "ica": calculate_cost('ICA', income),
        "stamps": calculate_cost('Estampillas', income),
        "cost_and_expenses": calculate_cost('Costos y gastos (Inicio del proyecto)', income),
    }

    # Cálculo de gastos y ganancias
    financial_data["expense"] = sum(
        [financial_data[key] for key in ["insurance_and_policies",
                                         "overhead", "unforeseen", "commission", "legal", "cost_and_expenses"]]
    )
    financial_data["four_x_mil"] = calculate_cost(
        '4 x Mil', cost + financial_data["expense"])
    financial_data["gross_profit"] = income - cost
    financial_data["ebitda"] = financial_data["gross_profit"] - \
        financial_data["expense"]
    financial_data["ebit"] = financial_data["ebitda"]
    financial_data["rent"] = calculate_cost(
        'Renta', financial_data["ebit"] - financial_data["financing"])
    financial_data["taxes"] = sum(
        [financial_data["ica"], financial_data["stamps"],
            financial_data["four_x_mil"], financial_data["rent"]]
    )
    financial_data["net_profit"] = financial_data["ebit"] - \
        financial_data["financing"] - financial_data["taxes"]

    # Redondear valores antes del cálculo de porcentajes
    for key in ["net_profit", "gross_profit", "ebitda", "ebit"]:
        financial_data[key] = round(financial_data[key])

    # Cálculo de porcentajes corregido
    percentage_data = {
        f"percentage_{key}": round((financial_data[key] / income) * 100) if income else 0
        for key in ["gross_profit", "ebitda", "ebit", "net_profit"]
    }

    return financial_data, percentage_data


def get_cost_values(env, financial_assessment_id=None):
    """
    Obtiene los valores de costos financieros desde la base de datos.

    :param env: Entorno de Odoo.
    :param financial_assessment_id: ID de la valoración financiera si ya existe.
    :return: Diccionario con los nombres y porcentajes de costos financieros.
    """

    if financial_assessment_id:
        # Buscar las líneas de costos financieros asociadas a la valoración guardada
        financial_lines = env['financial.assessment.line'].sudo().search([
            ('assessment_id', '=', financial_assessment_id)
        ])

        # Si existen líneas, devolver un diccionario con los valores almacenados
        if financial_lines:
            return {line.financial_costs_id.name: line.percentage for line in financial_lines}

    # Si no hay valoración guardada, obtener los valores actuales desde `financial.cost`
    return {cost.name: cost.percentage for cost in env['financial.cost'].sudo().search([])}


def get_financial_costs(env, partner_id, income, cost, financial_assessment_id=None, calculated_data=None):
    # Si se pasan datos calculados, se usan esos valores
    if calculated_data is not None:
        print("CONTIENE DATOS FINANCIEROS EDITADOS")
        financial_data = calculated_data['financial_data']
        percentage_data = calculated_data['percentage_data']
        # Se utiliza el cost_values enviado o, si no se envía, se obtiene por defecto
        cost_values = calculated_data.get(
            'cost_values', get_cost_values(env, financial_assessment_id))
    else:
        # Lógica original: obtener cost_values y recalcular los datos financieros
        cost_values = get_cost_values(env, financial_assessment_id)
        financial_data, percentage_data = calculate_financial_data(
            income, cost, cost_values)

    # Construir el nombre del cliente
    client_name = f"{partner_id.name} ({partner_id.identification_type_id.name}-{partner_id.vat})" if partner_id else 'N/A'

    # Cálculo del IVA y valor total
    iva_result = income * 0.19
    total_value = income + iva_result

    # Función para formatear valores como moneda (asegúrate de tener importado y configurado locale)
    def format_currency(value):
        return locale.format_string('%d', value, grouping=True).replace(',', '.')

    # Formatear los valores
    formatted_data = {key: format_currency(
        value) for key, value in financial_data.items()}
    formatted_data.update({
        "income_value": format_currency(income),
        "cost_value": format_currency(cost),
        "total_value": format_currency(total_value),
        "iva_result": format_currency(iva_result),
        **percentage_data
    })

    # Generar el HTML con los valores calculados
    def format_value(value):
        return f"$ {value}" if value != "0" else ""

    html = f'''
      <div style="display: grid; justify-items: center; margin-top: 25px; margin-bottom: 28px;">
      <table id="financial-table" border="1" cellpadding="5" cellspacing="0" style="width:80%; border-collapse:collapse; max-width: 1200px; font-size: 14px; table-layout: fixed; word-wrap: break-word;">
      <thead id="financial-header">
        <tr>
        <th id-field="description" style="border:1px solid black; width:25%; font-weight:bold;">NOMBRE DEL CLIENTE</th>
        <th class="name" colspan="3" style="border:1px solid black; text-align:center;">{client_name}</th>
        </tr>
        <tr>
        <th class="description" colspan="3" style="border:1px solid black; background-color:#D6DCE4;">Ingresos</th>
        <th class="valor" style="border:1px solid black; text-align:center; background-color:#FFFF00;">{format_value(formatted_data['income_value'])}</th>
        </tr>
        <tr>
        <th class="description" style="border:1px solid black; font-weight:bold;">IVA</th>
        <th class="percentage" style="border:1px solid black; text-align:center;">19%</th>
        <td style="border:1px solid black;"></td>
        <th class="valor" style="border:1px solid black; text-align:center;">{format_value(formatted_data['iva_result'])}</th>
        </tr>
        <tr>
        <th class="description" colspan="3" style="border:1px solid black; border-right:none; background-color:#02143f; color:#FFFFFF; font-weight:bold;">TOTAL</th>
        <th class="valor" style="border:1px solid black; text-align:center; background-color:#02143f; color:#FFFFFF;">{format_value(formatted_data['total_value'])}</th>
        </tr>
        <tr>
        <th style="border:1px solid black;border-right:none; text-align:center; color:#02143f; font-weight:bold; font-style:italic;">PYG GENERAL</th>
        <th style="border:1px solid black;"></th>
        <th style="border:1px solid black;"></th>
        <th style="border:1px solid black;"></th>
        </tr>
        <tr>
        <th style="border:1px solid black; text-align:center; color:#02143f; font-weight:bold; font-style:italic;">ESTADO DE RESULTADOS</th>
        <th style="border:1px solid black; text-align:center; color:#02143f; font-weight:bold; font-style:italic;"></th>
        <th style="border:1px solid black; text-align:center; color:#02143f; font-weight:bold; font-style:italic;">TOTALES</th>
        <th style="border:1px solid black; text-align:center; color:#02143f; font-weight:bold; font-style:italic;">%</th>
        </tr>
      </thead>
      <tbody id="financial-body">
        <tr>
        <td class="description" style="border:1px solid black;">Ingresos</td>
        <td style="border:1px solid black;"></td>
        <td class="valor" style="border:1px solid black; text-align:right;">{format_value(formatted_data['income_value'])}</td>
        <td style="border:1px solid black;"></td>
        </tr>
        <tr>
        <td class="description" style="border:1px solid black;">Costos</td>
        <td style="border:1px solid black;"></td>
        <td class="valor" style="border:1px solid black; text-align:right; background-color:#FFFF00;">{format_value(formatted_data['cost_value'])}</td>
        <td style="border:1px solid black;"></td>
        </tr>
        <tr>
        <td class="description" style="border:1px solid black; font-weight:bold; color:#375623;">Gastos</td>
        <td style="border:1px solid black;"></td>
        <td class="valor" style="border:1px solid black; text-align:right;">{format_value(formatted_data['expense'])}</td>
        <td style="border:1px solid black;"></td>
        </tr>
        <tr>
        <td class="description" style="border:1px solid black; background-color:#D6DCE4;">Utilidad Bruta</td>
        <td class="percentage" style="border:1px solid black; background-color:#D6DCE4;"></td>
        <td class="valor" style="border:1px solid black; text-align:right; background-color:#D6DCE4;">{format_value(formatted_data['gross_profit'])}</td>
        <td class="indicators_percentage" style="border:1px solid black; text-align:center; color:#02143f; font-weight:bold; font-style:italic;"> {f"{formatted_data['percentage_gross_profit']}%" if formatted_data['percentage_gross_profit'] != 0 else ""}</td>
        </tr>
        <tr>
        <td class="description" style="border:1px solid black;">Seguro y pólizas</td>
        <td class="percentage" style="border:1px solid black; text-align:center;">{f"{cost_values.get('Seguro y pólizas', 0)}%" if cost_values.get('Seguro y pólizas', 0) != 0 else ""}</td>
        <td class="valor" style="border:1px solid black; text-align:right;">{format_value(formatted_data['insurance_and_policies'])}</td>
        <td style="border:1px solid black;"></td>
        </tr>
        <tr>
        <td class="description" style="border:1px solid black;">Overhead</td>
        <td class="percentage" style="border:1px solid black; text-align:center;">{f"{cost_values.get('Overhead', 0)}%" if cost_values.get('Overhead', 0) != 0 else ""}</td>
        <td class="valor" style="border:1px solid black; text-align:right;">{format_value(formatted_data['overhead'])}</td>
        <td style="border:1px solid black;"></td>
        </tr>
        <tr>
        <td class="description" style="border:1px solid black;">Imprevistos</td>
        <td class="percentage" style="border:1px solid black; text-align:center;">{f"{cost_values.get('Imprevistos', 0)}%" if cost_values.get('Imprevistos', 0) != 0 else ""}</td>
        <td class="valor" style="border:1px solid black; text-align:right;">{format_value(formatted_data['unforeseen'])}</td>
        <td style="border:1px solid black;"></td>
        </tr>
        <tr>
        <td class="description" style="border:1px solid black;">Comisión</td>
        <td class="percentage" style="border:1px solid black; text-align:center;">{f"{cost_values.get('Comisión', 0)}%" if cost_values.get('Comisión', 0) != 0 else ""}</td>
        <td class="valor" style="border:1px solid black; text-align:right;">{format_value(formatted_data['commission'])}</td>
        <td style="border:1px solid black;"></td>
        </tr>
        <tr>
        <td class="description" style="border:1px solid black;">Costos y gastos</td>
        <td class="percentage" style="border:1px solid black; text-align:center;">{f"{cost_values.get('Costos y gastos (Inicio del proyecto)', 0)}%" if cost_values.get('Costos y gastos (Inicio del proyecto)', 0) != 0 else ""}</td>
        <td class="valor" style="border:1px solid black; text-align:right;">{format_value(formatted_data['cost_and_expenses'])}</td>
        <td style="border:1px solid black;"></td>
        </tr>
        <tr>
        <td class="description" style="border:1px solid black;">Jurídico</td>
        <td class="percentage" style="border:1px solid black; text-align:center;">{f"{cost_values.get('Jurídico', 0)}%" if cost_values.get('Jurídico', 0) != 0 else ""}</td>
        <td class="valor" style="border:1px solid black; text-align:right;">{format_value(formatted_data['legal'])}</td>
        <td style="border:1px solid black;"></td>
        </tr>
        <tr>
        <td class="description" style="border:1px solid black; background-color:#D6DCE4;">EBITDA</td>
        <td class="percentage" style="border:1px solid black; text-align:center; background-color:#D6DCE4;"></td>
        <td class="valor" style="border:1px solid black; text-align:right; background-color:#D6DCE4;">{format_value(formatted_data['ebitda'])}</td>
        <td class="indicators_percentage" style="border:1px solid black; text-align:center; color:#02143f; font-weight:bold; font-style:italic;"> {f"{formatted_data['percentage_ebitda']}%" if formatted_data['percentage_ebitda'] != 0 else ""}</td>
        </tr>
        <tr>
        <td class="description" style="border:1px solid black; background-color:#D6DCE4;">EBIT</td>
        <td class="percentage" style="border:1px solid black; text-align:center; background-color:#D6DCE4;"></td>
        <td class="valor" style="border:1px solid black; text-align:right; background-color:#D6DCE4;">{format_value(formatted_data['ebit'])}</td>
        <td class="indicators_percentage" style="border:1px solid black; text-align:center; color:#02143f; font-weight:bold; font-style:italic;"> {f"{formatted_data['percentage_ebit']}%" if formatted_data['percentage_ebit'] != 0 else ""}</td>
        </tr>
        <tr>
        <td class="description" style="border:1px solid black; background-color:#D6DCE4;">FINANCIACION</td>
        <td class="percentage" style="border:1px solid black; text-align:center; background-color:#D6DCE4;">{f"{cost_values.get('FINANCIACION', 0)}%" if cost_values.get('FINANCIACION', 0) != 0 else ""}</td>
        <td class="valor" style="border:1px solid black; text-align:right; background-color:#D6DCE4;">{format_value(formatted_data['financing'])}</td>
        <td style="border:1px solid black;"></td>
        </tr>
        <tr>
        <td class="description" style="border:1px solid black; background-color:#D6DCE4;">IMPUESTOS</td>
        <td style="border:1px solid black; text-align:center; background-color:#D6DCE4;"></td>
        <td class="valor" style="border:1px solid black; text-align:right; background-color:#D6DCE4;">{format_value(formatted_data['taxes'])}</td>
        <td style="border:1px solid black;"></td>
        </tr>
        <tr>
        <td class="description" style="border:1px solid black;">ICA</td>
        <td class="percentage" style="border:1px solid black; text-align:center;">{f"{cost_values.get('ICA', 0)}%" if cost_values.get('ICA', 0) != 0 else ""}</td>
        <td class="valor" style="border:1px solid black; text-align:right;">{format_value(formatted_data['ica'])}</td>
        <td style="border:1px solid black;"></td>
        </tr>
        <tr>
        <td class="description" style="border:1px solid black;">Estampillas</td>
        <td class="percentage" style="border:1px solid black; text-align:center;">{f"{cost_values.get('Estampillas', 0)}%" if cost_values.get('Estampillas', 0) != 0 else ""}</td>
        <td class="valor" style="border:1px solid black; text-align:right;">{format_value(formatted_data['stamps'])}</td>
        <td style="border:1px solid black;"></td>
        </tr>
        <tr>
        <td class="description" style="border:1px solid black;">4 x Mil</td>
        <td class="percentage" style="border:1px solid black; text-align:center;">{f"{cost_values.get('4 x Mil', 0)}%" if cost_values.get('4 x Mil', 0) != 0 else ""}</td>
        <td class="valor" style="border:1px solid black; text-align:right;">{format_value(formatted_data['four_x_mil'])}</td>
        <td style="border:1px solid black;"></td>
        </tr>
        <tr>
        <td class="description" style="border:1px solid black;">Renta</td>                      
        <td class="percentage" style="border:1px solid black; text-align:center;">{f"{cost_values.get('Renta', 0)}%" if cost_values.get('Renta', 0) != 0 else ""}</td>
        <td class="valor" style="border:1px solid black; text-align:right;">{format_value(formatted_data['rent'])}</td>                        
        <td style="border:1px solid black;"></td>
        </tr>
        <tr>
        <td class="description" style="border:1px solid black; background-color:#D6DCE4;">Utilidad Neta</td>
        <td class="percentage" style="border:1px solid black; text-align:center; background-color:#D6DCE4;"></td>
        <td class="valor" style="border:1px solid black; text-align:right; background-color:#D6DCE4;">{format_value(formatted_data['net_profit'])}</td>
        <td class="indicators_percentage" style="border:1px solid black; text-align:center; color:#02143f; font-weight:bold; font-style:italic;"> {f"{formatted_data['percentage_net_profit']}%" if formatted_data['percentage_net_profit'] != 0 else ""}</td>
        </tr>
        <tr>
        <td style="border:1px solid black; color:#833C0C; font-weight:bold; font-style:italic;">INDICADORES</td>
        <td style="border:1px solid black;"></td>
        <td style="border:1px solid black;"></td>
        <td style="border:1px solid black;"></td>
        </tr>
        <tr>
        <td class="indicators_description" style="border:1px solid black;">Utilidad Bruta</td>
        <td style="border:1px solid black; text-align:right;"></td>
        <td class="indicators_percentage" style="border:1px solid black; text-align:center; font-weight:bold;">{f"{formatted_data['percentage_gross_profit']}%" if formatted_data['percentage_gross_profit'] != 0 else ""}</td>
        <td style="border:1px solid black;"></td>
         </tr>
        <tr>
        <td class="indicators_description" style="border:1px solid black;">Ebitda</td>
        <td style="border:1px solid black; text-align:right;"></td>
        <td class="indicators_percentage" style="border:1px solid black; text-align:center; font-weight:bold;">{f"{formatted_data['percentage_ebitda']}%" if formatted_data['percentage_ebitda'] != 0 else ""}</td>
        <td style="border:1px solid black;"></td>
        </tr>
        <tr>
        <td class="indicators_description" style="border:1px solid black;">EBIT</td>
        <td style="border:1px solid black; text-align:right;"></td>
        <td class="indicators_percentage" style="border:1px solid black; text-align:center; font-weight:bold;">{f"{formatted_data['percentage_ebit']}%" if formatted_data['percentage_ebit'] != 0 else ""}</td>
        <td style="border:1px solid black;"></td>
        </tr>
        <tr>
        <td class="indicators_description" style="border:1px solid black;">Utilidad Neta</td>
        <td style="border:1px solid black; text-align:right;"></td>
        <td class="indicators_percentage" style="border:1px solid black; text-align:center; font-weight:bold;">{f"{formatted_data['percentage_net_profit']}%" if formatted_data['percentage_net_profit'] != 0 else ""}</td>
        <td style="border:1px solid black;"></td>
        </tr>
      </tbody>
      </table>

      </div>
      '''

    return html
