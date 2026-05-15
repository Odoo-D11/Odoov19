/** @odoo-module **/
import { registry } from "@web/core/registry";
import { CharField, charField } from "@web/views/fields/char/char_field";
import { Component, useState } from "@odoo/owl";

export class BankAccountField extends CharField {
    static template = "BankAccountFieldTemplate";

    setup() {
        super.setup();
        this.state = useState({
            isVisible: false
        });
    }

    get displayValue() {
        const value = this.props.record.data[this.props.name] || '';
        if (!value) return '';
        
        if (this.state.isVisible) {
            return this.formatBankAccount(value);
        } else {
            return this.maskBankAccount(value);
        }
    }

    get inputValue() {
        const value = this.props.record.data[this.props.name] || '';
        if (!value) return '';
        
        if (this.state.isVisible) {
            return this.formatBankAccount(value);
        } else {
            return this.maskBankAccount(value);
        }
    }

    formatBankAccount(account) {
        if (!account) return '';
        return account.replace(/(\d{3})(?=\d)/g, '$1-');
    }

    maskBankAccount(account) {
        if (!account || account.length < 4) return account;
        const lastThreeDigits = account.slice(-3);
        const totalLength = account.length;
        const maskedLength = totalLength - 3;
        const maskedGroups = Math.ceil(maskedLength / 3);
        const maskedPart = Array(maskedGroups).fill('XXX').join('-');
        
        return maskedPart + '-' + lastThreeDigits;
    }

    onToggleVisibility() {
        this.state.isVisible = !this.state.isVisible;
        if (this.inputRef && this.inputRef.el) {
            const value = this.props.record.data[this.props.name] || '';
            this.inputRef.el.value = this.state.isVisible ? 
                this.formatBankAccount(value) : 
                this.maskBankAccount(value);
        }
    }

    get showToggleButton() {
        const value = this.props.record.data[this.props.name] || '';
        return value.length > 0;
    }

    get eyeIcon() {
        return this.state.isVisible ? 'fa-eye-slash' : 'fa-eye';
    }

    get eyeTitle() {
        return this.state.isVisible ? 'Ocultar número completo' : 'Mostrar número completo';
    }

    onInputChange(ev) {
        let value = ev.target.value.replace(/[^0-9]/g, '');
        this.props.record.data[this.props.name] = value;
        ev.target.value = this.state.isVisible ? 
            this.formatBankAccount(value) : 
            this.maskBankAccount(value);
    }
}

registry.category("fields").add("BankAccount", {
    ...charField,
    component: BankAccountField,
    displayName: "Cuenta Bancaria",
    supportedTypes: ["char"],
});
