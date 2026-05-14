# -*- coding: utf-8 -*-
import logging
import requests

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResCurrencyRate(models.Model):
    _inherit = "res.currency.rate"

    @api.model
    def cron_sync_trm_and_derived_rates(self, date=None, company=None):
        """Sincroniza TRM oficial USD/COP y tasas derivadas para otras monedas."""
        company = company or self.env.company
        date = date or fields.Date.today()

        cop = company.currency_id
        if cop.name != "COP":
            _logger.warning(
                "Este sincronizador asume moneda base COP. company=%s", company.id)
            return

        cop_per_usd, effective_date = self._fetch_trm_usd_cop_effective(date)

        currencies = self.env["res.currency"].search([
            ("active", "=", True),
            ("id", "!=", cop.id),
        ])

        for ccy in currencies:
            code = ccy.name

            # COP por 1 unidad
            if code == "USD":
                cop_per_unit = cop_per_usd
            else:
                usd_per_unit = self._fetch_usd_per_unit(code)
                if not usd_per_unit:
                    _logger.info("No se pudo obtener %s->USD; se omite.", code)
                    continue
                cop_per_unit = usd_per_unit * cop_per_usd  # triangulación

            vals = {
                "name": effective_date,            # fecha vigencia
                "company_id": company.id,
                "currency_id": ccy.id,
                "inverse_company_rate": cop_per_unit,     # COP por 1 unidad
                "company_rate": 1.0 / cop_per_unit,       # 1 COP en unidades de la moneda
            }

            rate = self.search([
                ("name", "=", vals["name"]),
                ("company_id", "=", company.id),
                ("currency_id", "=", ccy.id),
            ], limit=1)

            if rate:
                rate.write(vals)
            else:
                self.create(vals)

    # ---------- Fuentes ----------

    def _fetch_trm_usd_cop_effective(self, date_):
        """
        Devuelve TRM oficial USD/COP y fecha de vigencia.
        """
        url = "https://www.datos.gov.co/resource/32sa-8pi3.json"
        dt = f"{date_}T00:00:00.000"

        # 1) Intentar tasa vigente para el día
        soql = (
            "SELECT valor, vigenciadesde, vigenciahasta "
            f"WHERE vigenciadesde <= '{dt}' AND vigenciahasta >= '{dt}' "
            "ORDER BY vigenciadesde DESC LIMIT 1"
        )
        r = requests.get(url, params={"$query": soql}, timeout=15)
        r.raise_for_status()
        data = r.json()

        # 2) Fallback: último registro disponible
        if not data:
            r = requests.get(
                url,
                params={
                    "$query": "SELECT valor, vigenciadesde, vigenciahasta ORDER BY vigenciahasta DESC LIMIT 1"},
                timeout=15,
            )
            r.raise_for_status()
            data = r.json()

        if not data:
            raise Exception("No fue posible obtener TRM desde datos.gov.co")

        row = data[0]
        cop_per_usd = float(
            str(row["valor"]).replace("$", "").replace(",", ""))
        eff_date = row.get("vigenciadesde", "").split("T")[0] or str(date_)
        return cop_per_usd, fields.Date.from_string(eff_date)

    def _fetch_usd_per_unit(self, code):
        """
        Devuelve USD por 1 unidad de la moneda indicada.
        """
        try:
            r = requests.get(
                f"https://open.er-api.com/v6/latest/{code}", timeout=15)
            r.raise_for_status()
            payload = r.json()
            rates = payload.get("rates") or {}
            return float(rates.get("USD")) if rates.get("USD") else None
        except Exception:
            return None
