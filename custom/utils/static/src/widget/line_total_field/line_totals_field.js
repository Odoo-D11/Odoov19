/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState } from "@odoo/owl";
import { useRecordObserver } from "@web/model/relational_model/utils";
import { formatMonetary as formatMonetaryValue, formatFloat } from "@web/views/fields/formatters";
import { parseFloat as parseFloatValue } from "@web/views/fields/parsers";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const COP_CURRENCY_ID = 8;

export const LineTotalsField = {
    component: class LineTotalsField extends Component {
        static template = "utils.LineTotalsField";
        static props = {
            ...standardFieldProps,
        };

        setup() {
            this.state = useState({
                subtotal: 0,
                total: 0,
                currencyId: this._getCurrencyId(this.props.record),
                localCurrencyId: this._getLocalCurrencyId(this.props.record),
                localTotal: undefined,
                showTrm: false,
            });

            useRecordObserver((record) => {
                const totals = this._computeTotals(record);
                const currentValue = this._normalizeNumber(record.data[this.props.name]);
                if (
                    record.isInEdition &&
                    totals.total !== null &&
                    !this._isAlmostEqual(currentValue, totals.total)
                ) {
                    record.update({ [this.props.name]: totals.total });
                }
                Object.assign(this.state, totals);
            });
        }

        _computeTotals(record) {
            const subtotalFromLines = this._computeSubtotal(record);
            const currencyId = this._getCurrencyId(record);
            const localCurrencyId = this._getLocalCurrencyId(record);
            const trmValue = this._getTrmValue(record);
            const isCopCurrency = this._isCopCurrency(record);
            const hasTrmField =
                record && record.data && Object.prototype.hasOwnProperty.call(record.data, "trm");
            if (subtotalFromLines === null) {
                const storedTotal = this._normalizeNumber(record.data[this.props.name]);
                return {
                    subtotal: storedTotal,
                    total: storedTotal,
                    currencyId,
                    localCurrencyId,
                    localTotal: undefined,
                    showTrm: false,
                };
            }
            if (trmValue > 0) {
                const totalInLocalCurrency = subtotalFromLines * trmValue;
                if (hasTrmField && !isCopCurrency) {
                    return {
                        total: subtotalFromLines,
                        localTotal: totalInLocalCurrency,
                        subtotal: subtotalFromLines,
                        currencyId,
                        localCurrencyId,
                        showTrm: true,
                    };
                }
            }
            return {
                subtotal: subtotalFromLines,
                total: subtotalFromLines,
                currencyId,
                localCurrencyId,
                localTotal: undefined,
                showTrm: false,
            };
        }

        _computeSubtotal(record) {
            const linesList = record.data.product_line_ids;
            if (!linesList || !Array.isArray(linesList.records)) {
                return null;
            }
            let subtotal = 0;
            for (const line of linesList.records) {
                if (!line || !line.data || line.data.display_type) {
                    continue;
                }
                subtotal += this._getLineSubtotal(line);
            }
            return subtotal;
        }

        _getLineSubtotal(line) {
            const { data = {} } = line;
            if (typeof data.subtotal === "number") {
                return data.subtotal;
            }
            if (typeof data.subtotal === "string" && data.subtotal.trim()) {
                try {
                    return parseFloatValue(data.subtotal);
                } catch {
                    // fallback to manual computation
                }
            }
            const qty = this._normalizeNumber(data.qty);
            const price = this._normalizeNumber(data.price_unit);
            return qty * price;
        }

        _normalizeNumber(value) {
            if (typeof value === "number") {
                return value;
            }
            if (typeof value === "string" && value.trim()) {
                try {
                    return parseFloatValue(value);
                } catch {
                    return 0;
                }
            }
            return 0;
        }

        _isAlmostEqual(a, b) {
            return Math.abs((a || 0) - (b || 0)) < 0.00001;
        }

        _getCurrencyId(record) {
            const currency = record.data.currency_id;
            return this._parseCurrencyId(currency);
        }

        _getLocalCurrencyId(record) {
            if (record?.data?.company_currency_id !== undefined) {
                const recordCurrencyId = this._parseCurrencyId(record.data.company_currency_id);
                if (recordCurrencyId !== undefined) {
                    return recordCurrencyId;
                }
            }
            const envCompanyCurrency = this.env?.company?.currency_id;
            const envCurrencyId = this._parseCurrencyId(envCompanyCurrency);
            if (envCurrencyId !== undefined) {
                return envCurrencyId;
            }
            return COP_CURRENCY_ID;
        }

        _parseCurrencyId(currency) {
            if (Array.isArray(currency)) {
                return currency[0];
            }
            if (currency && typeof currency === "object") {
                if ("id" in currency) {
                    return currency.id;
                }
                if ("res_id" in currency) {
                    return currency.res_id;
                }
            }
            return typeof currency === "number" ? currency : undefined;
        }

        _getTrmValue(record) {
            const trm = record.data.trm || 0;
            return this._normalizeNumber(trm);
        }

        _extractCurrencyIdentifiers(currency) {
            const identifiers = [];
            if (!currency) {
                return identifiers;
            }
            if (Array.isArray(currency)) {
                if (currency.length > 1 && typeof currency[1] === "string") {
                    identifiers.push(currency[1]);
                }
            } else if (typeof currency === "object") {
                const possibleKeys = ["display_name", "name", "code"];
                for (const key of possibleKeys) {
                    if (typeof currency[key] === "string") {
                        identifiers.push(currency[key]);
                    }
                }
            } else if (typeof currency === "string") {
                identifiers.push(currency);
            }
            return identifiers;
        }

        _isCopIdentifier(identifier) {
            return typeof identifier === "string" && identifier.toUpperCase().includes("COP");
        }

        _isCopCurrency(record) {
            const currency = record?.data?.currency_id;
            if (!currency) {
                return false;
            }
            const companyCurrency = record?.data?.company_currency_id ?? this.env?.company?.currency_id;
            const currencyId = this._parseCurrencyId(currency);
            const companyCurrencyId = this._parseCurrencyId(companyCurrency);
            if (currencyId !== undefined && companyCurrencyId !== undefined) {
                return currencyId === companyCurrencyId;
            }
            const recordIdentifiers = this._extractCurrencyIdentifiers(currency);
            const companyIdentifiers = this._extractCurrencyIdentifiers(companyCurrency);
            if (recordIdentifiers.length && companyIdentifiers.length) {
                const hasMatch = recordIdentifiers.some((identifier) =>
                    companyIdentifiers.some(
                        (companyIdentifier) =>
                            typeof identifier === "string" &&
                            typeof companyIdentifier === "string" &&
                            identifier.toUpperCase() === companyIdentifier.toUpperCase()
                    )
                );
                if (hasMatch) {
                    return true;
                }
            }
            return recordIdentifiers.some((identifier) => this._isCopIdentifier(identifier));
        }

        formatMonetary(value, currencyId) {
            const amount = value === null || value === undefined ? 0 : value;
            const effectiveCurrencyId =
                currencyId !== undefined ? currencyId : this.state.currencyId;
            if (effectiveCurrencyId) {
                return formatMonetaryValue(amount, { currencyId: effectiveCurrencyId });
            }
            const digits = this.props.field && this.props.field.digits;
            return formatFloat(amount, { digits });
        }

        get showTotals() {
            return Number.isFinite(this.state.total ?? 0);
        }

        get showTotalDivider() {
            return !this._isAlmostEqual(this.state.subtotal, this.state.total);
        }
    },
    supportedTypes: ["monetary", "float", "integer"],
};

registry.category("fields").add("line-totals-field", LineTotalsField);
