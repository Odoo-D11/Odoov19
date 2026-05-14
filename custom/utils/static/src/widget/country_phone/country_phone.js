/** @odoo-module **/

import { registry } from '@web/core/registry';
import { PhoneField } from "@web/views/fields/phone/phone_field";
import { useState, useEffect } from '@odoo/owl';
import { useService } from "@web/core/utils/hooks";

class PhoneWithCountryWidget extends PhoneField {
    static template = "PhoneWithCountryWidgetTemplate";
    static components = { PhoneField };

    setup() {
        super.setup();

        this.orm = useService('orm');
        this.state = useState({
            countryFlagUrl: '',
            countryCallingCode: '',
        });

        useEffect(
            () => {
                this.updateCountryInfo();
            },
            () => [this.props.record.data.country_id]
        );
    }

    async updateCountryInfo() {
        const countryData = this.props.record.data.country_id;
        const countryId = countryData && (Array.isArray(countryData) ? countryData[0] : countryData.id);
        if (countryId) {
            try {
                const countryInfo = await this.orm.read('res.country', [countryId], ['phone_code', 'image_url']);
                if (countryInfo && countryInfo.length > 0) {
                    const country = countryInfo[0];
                    this.state.countryFlagUrl = country.image_url;
                    this.state.countryCallingCode = `+${country.phone_code}`;
                }
            } catch (error) {
                console.error('Error fetching country info:', error);
            }
        } else {
            this.state.countryFlagUrl = '';
            this.state.countryCallingCode = '';
        }
    }
}

PhoneWithCountryWidget.supportedTypes = ['char'];

registry.category('fields').add('CodeCountryPhone', { component: PhoneWithCountryWidget });

