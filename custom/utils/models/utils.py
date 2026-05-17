# -*- coding: utf-8 -*-

from odoo import api, SUPERUSER_ID, _
from odoo.exceptions import ValidationError
import re
from html.parser import HTMLParser
from html import unescape
import unicodedata
from bs4 import BeautifulSoup
import validators
import string


def _clean_name(name):
    # Eliminar puntos
    name = re.sub(r'\.', '', name)
    # Formatear palabras entre paréntesis
    name = re.sub(r'\(([^)]+)\)',
                    lambda m: f"({m.group(1).capitalize()})", name)
    # Eliminar paréntesis de apertura sin cierre
    name = re.sub(r'\([^)]*$', '', name)
    # Unir palabras separadas por puntos
    name = re.sub(r'\s*\.\s*', '', name)
    # Eliminar espacios adicionales
    name = re.sub(r'\s+', ' ', name).strip()
    # Eliminar tildes y caracteres especiales para la comparación
    name = ''.join((c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn'))
    # Convertir a mayúsculas si el nombre tiene 4 caracteres o menos
    if len(name) <= 4:
        name = name.upper()
    else:
        # Convertir a mayúsculas la primera letra de cada palabra
        name = string.capwords(name)
    return name

def is_html_content_empty(value):
    """
    Verifica si un campo HTML está vacío o contiene únicamente caracteres insignificantes.
    """
    try:
        # print("Original value:", value)
        if not value:  # Si el valor es None o está vacío
            return True

        # Convierte entidades HTML (&nbsp;, &amp;, etc.) en texto plano
        cleaned_value = unescape(value)
        # Elimina etiquetas HTML
        cleaned_value = re.sub(r'<[^>]*>', '', cleaned_value).strip()

        # print("Cleaned value after HTML processing:", cleaned_value)

        # Si el contenido está vacío después de limpiar
        if not cleaned_value:
            return True

        # Verificar si contiene solo caracteres no significativos
        insignificant_pattern = r'^[\s.,@#?!&$%^*(){}[\]:;"\'<>\-/\\]+$'
        if re.match(insignificant_pattern, cleaned_value):
            # print("Matched as insignificant content")
            return True

        # Verificar si contiene solo caracteres no imprimibles o emojis
        for char in cleaned_value:
            if not (char.isspace() or
                    unicodedata.category(char) in ('Zs', 'Cc', 'Cf') or
                    unicodedata.name(char, '').startswith('EMOJI')):
                # Si al menos un carácter es significativo, no está vacío
                print("Found significant character:", char)
                return ""

        # print("All characters are insignificant")
        return True

    except Exception as e:
        # Log para depuración en caso de error inesperado
        # print("Error en is_html_content_empty:", e)
        return True  # Considerar vacío si ocurre un error inesperado


def format_html_to_sentence_case(value):
    """
    Convierte el contenido HTML en texto con la primera letra en mayúscula y el resto en minúscula.
    - Unifica los párrafos consecutivos en un solo bloque.
    - Preserva listas, tablas y otros elementos HTML estructurales.
    - Elimina nodos vacíos como <p><br></p>.
    - Elimina estilos como negrilla, cursiva, subrayado, etc., sin unir palabras.
    - Elimina espacios adicionales
    """
    if not value:
        return value

    soup = BeautifulSoup(value, 'html.parser')

    def transform_text_node(text):
        """Convierte texto plano a Sentence Case."""
        text = text.strip()  # Elimina espacios adicionales
        return text[:1].upper() + text[1:].lower() if text else ""

    # Remover etiquetas de formato como <b>, <strong>, <i>, <em>, <u>
    for tag in soup.find_all(['b', 'strong', 'i', 'em', 'u']):
        tag.unwrap()  # Mantiene el texto, pero elimina la etiqueta

    # Combinar todos los párrafos consecutivos en un solo bloque
    paragraphs = []
    for element in soup.find_all(recursive=""):
        if element.name in ['p', 'div']:  # Si el elemento es un párrafo o un div
            paragraphs.append(element.get_text(strip=True))
            element.extract()  # Eliminar el elemento original
        elif paragraphs:
            new_paragraph = soup.new_tag('p')
            combined_text = ' '.join(paragraphs)  # Unir los textos
            new_paragraph.string = transform_text_node(combined_text)
            soup.insert(0, new_paragraph)
            paragraphs = []

    if paragraphs:
        new_paragraph = soup.new_tag('p')
        combined_text = ' '.join(paragraphs)
        new_paragraph.string = transform_text_node(combined_text)
        soup.append(new_paragraph)

    # Transformar nodos de texto dentro de listas o tablas
    for element in soup.find_all(string=True):
        if element.parent.name not in ['style', 'script']:
            element.replace_with(transform_text_node(element))

    # Eliminar nodos <p> vacíos o que contengan solo <br>
    for p in soup.find_all('p'):
        if not p.get_text(strip=True) and not p.find_all('img'):
            p.extract()

    # Eliminar espacios adicionales en el HTML resultante
    html_str = str(soup)
    html_str = re.sub(r'\s+', ' ', html_str).strip()
    soup = BeautifulSoup(html_str, 'html.parser')

    return str(soup)


def convert_first_letter_to_uppercase(value):
    """
    Convierte la primera letra de una cadena de texto en mayúscula y el resto en minúsculas.
    Si hay espacios al inicio se eliminan.
    """
    if not value:
        return ""
    # Quitar espacios al inicio, conservar el resto tal cual
    value = str(value).lstrip()
    if not value:
        return ""
    return value[:1].upper() + value[1:].lower()


def is_valid_url(url):
    """
    Valida si una URL es válida.

    :param url: (str) URL a validar.
    :return: (bool) True si es válida, False si no lo es.
    """
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if not url:
        return False

    # Validar esquema y netloc usando urlparse
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    scheme = (parsed.scheme or '').lower()
    if scheme not in ('http', 'https', 'ftp'):
        return False
    if not parsed.netloc:
        return False

    # Verificación con la librería validators como filtro adicional,
    # asegurando que el resultado sea evaluado como booleano.
    try:
        valid = validators.url(url)
    except Exception:
        valid = False
    if not bool(valid):
        return False

    # Expresión regular para una validación extra y más estricta
    url_regex = re.compile(
        # Protocolo (http, https, ftp)
        r'^(https?|ftp)://'
        r'('
        r'([A-Za-z0-9-]+\.)+[A-Za-z]{2,63}'   # Dominio con TLD (2-63 chars)
        r'|localhost'                         # localhost
        r'|\d{1,3}(\.\d{1,3}){3}'             # IP
        r')'
        r'(:\d+)?'                                # Puerto opcional
        r'(/.*)?$',                               # Ruta opcional
        re.IGNORECASE
    )

    return url_regex.match(url) is not None
