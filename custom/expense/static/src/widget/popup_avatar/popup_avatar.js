/** @odoo-module **/
import { registry } from "@web/core/registry";
import { buildM2OFieldDescription, Many2OneField } from "@web/views/fields/many2one/many2one_field";
import { useState, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class ExpPartnerPopup extends Many2OneField {
    static template = "ExpPartnerPopupTemplate";

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.partnerId = this.props.record.data[this.props.name]?.id || null;
        this.personalInfo = useState({ exists: false, id: null, ready: false, partnerId: this.partnerId });
        onWillStart(async () => {
            await this._checkPersonalInfo();
        });
        onWillUpdateProps(async (newProps) => {
            const newPartnerId = newProps.record.data[newProps.name]?.id || null;
            if (newPartnerId !== this.partnerId) {
                this.partnerId = newPartnerId;
                this.personalInfo.partnerId = newPartnerId;
                await this._checkPersonalInfo();
            }
        });
    }

    async _checkPersonalInfo() {
        this.personalInfo.ready = false;
        this.personalInfo.exists = false;
        this.personalInfo.id = null;
        this.personalInfo.partnerId = this.partnerId;
        if (!this.partnerId) {
            this.personalInfo.ready = true;
            return;
        }
        const infos = await this.orm.searchRead(
            "expense.personal.information",
            [["partner_id", "=", this.partnerId]],
            ["id", "partner_id"],
            { limit: 1 }
        );
        if (infos.length) {
            this.personalInfo.exists = true;
            this.personalInfo.id = infos[0].id;
        }
        this.personalInfo.ready = true;
    }

    async openPersonalInfo() {
        if (!this.partnerId) return;
        const expenseId = this.props.record.resId;
        const state = this.props.record.data.state;
        const changes = this.props.record._changes || {};
        const isPartnerChanged = Object.prototype.hasOwnProperty.call(changes, "partner_id");
        if (!expenseId) {
            if (this.personalInfo.exists) {
                this.notification.add(
                    "Para consultar la información personal del contacto, primero debe guardar la solicitud.",
                    { type: "danger" }
                );
            } else {
                this.notification.add(
                    "Para agregar la información personal del contacto, primero debe guardar la solicitud. Por favor, verifique e intente nuevamente.",
                    { type: "danger" }
                );
            }
            return;
        }
        if (state !== 'draft' && isPartnerChanged) {
            this.notification.add(
                "No se puede modificar la información personal del contacto porque la solicitud no está en estado Borrador y el contacto fue cambiado. Deshaga los cambios o contacte al área responsable.",
                { type: "danger" }
            );
            return;
        }
        let context = {};
        let flags = {};
        if (state !== 'draft') {
            flags = { mode: 'readonly' };
        }
        if (!this.personalInfo.exists) {
            const employees = await this.orm.searchRead(
                "hr.employee",
                [["work_contact_id", "=", this.partnerId]],
                ["id", "work_contact_id", "name", "job_title", "identification_type_id", "identification_id", "work_email", "mobile_phone", "birthday"]
            );
            if (employees.length) {
                const emp = employees[0];
                let identification_type_id = emp.identification_type_id?.[0] || false;
                let identification_type_code = emp.identification_type_id?.[1] || "";
                let nuid = emp.identification_id || "";
                if (identification_type_code === "NIT") {
                    identification_type_id = false;
                    nuid = "";
                }
                context = {
                    default_sequence: this.partnerId,
                    default_partner_id: emp.work_contact_id?.[0] || this.partnerId,
                    default_job_title: emp.job_title || "",
                    default_identification_type_id: identification_type_id,
                    default_nuid: nuid,
                    default_email: emp.work_email || "",
                    default_phone: emp.mobile_phone || "",
                    default_birth_date: emp.birthday || "",
                };
            } else {
                const [partner] = await this.orm.searchRead(
                    "res.partner",
                    [["id", "=", this.partnerId]],
                    ["id", "name", "email", "phone", "identification_type_id", "vat"]
                );
                let identification_type_id = partner.identification_type_id?.[0] || false;
                let identification_type_code = partner.identification_type_id?.[1] || "";
                let nuid = partner.vat || "";
                if (identification_type_code === "NIT") {
                    identification_type_id = false;
                    nuid = "";
                }
                context = {
                    default_sequence: partner.id,
                    default_partner_id: partner.id,
                    default_job_title: "",
                    default_identification_type_id: identification_type_id,
                    default_nuid: nuid,
                    default_email: partner.email || "",
                    default_phone: partner.phone || "",
                    default_birth_date: "",
                };
            }
        }
        await this.actionService.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "expense.personal.information",
                res_id: this.personalInfo.id || false,
                views: [[false, "form"]],
                target: "new",
                context: context,
                flags: flags,
            },
            {
                onClose: async () => {
                    await this._checkPersonalInfo();
                },
            }
        );
    }
}

registry.category("fields").add("ExpPartnerPopup", {
    ...buildM2OFieldDescription(ExpPartnerPopup),
    displayName: "Información personal (Contacto)",
});
