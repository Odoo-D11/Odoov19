/** @odoo-module **/

import { registry } from '@web/core/registry';
import { DateTimeField } from "@web/views/fields/datetime/datetime_field";
import { onMounted, onPatched } from '@odoo/owl';

class RemainDaysDatetime extends DateTimeField {
    static template = "WidgetRemainingDaysTemplate";

    setup() {
        super.setup();

        // Validar si `name` está definido
        if (!this.props?.name) {
            return;
        }

        // Establecer el placeholder al montar y actualizar el componente
        onMounted(() => {
            this.setPlaceholderDirectly();
        });

        onPatched(() => {
            this.setPlaceholderDirectly();
        });
    }

    setPlaceholderDirectly() {
        const inputElements = document.querySelectorAll('input[type="text"][data-field]');
        inputElements.forEach(inputElement => {
            if (inputElement && inputElement.getAttribute('data-field') === this.props.name) {
                const randomDate = new Date();
                randomDate.setDate(randomDate.getDate() + Math.floor(Math.random() * 365)); // Fecha al azar dentro del próximo año
                const randomDateString = randomDate.toISOString().split('T')[0];

                inputElement.setAttribute('placeholder', `Ej. ${randomDateString}`);
            }
        });
    }

    getRemainingDays() {
        if (!this.props?.record?.data || !this.props?.name) {
            return '';
        }

        const targetDateStr = this.props.record.data[this.props.name];
        if (!targetDateStr) {
            return '';
        }

        // Normalizar las fechas para que ambas estén a medianoche
        const targetDate = new Date(targetDateStr);
        targetDate.setHours(0, 0, 0, 0);
        const today = new Date();
        today.setHours(0, 0, 0, 0);

        const timeDiff = targetDate - today;
        const daysRemaining = Math.floor(timeDiff / (1000 * 60 * 60 * 24));

        if (daysRemaining < 0) {
            return `- Finalizó hace ${Math.abs(daysRemaining)} ${Math.abs(daysRemaining) === 1 ? 'día' : 'días'}`;
        } else if (daysRemaining === 0) {
            return `- Finaliza hoy`;
        } else {
            return `- Finaliza en ${daysRemaining} ${daysRemaining === 1 ? 'día' : 'días'}`;
        }
    }

    getRemainingDaysColor() {
        const daysRemaining = this.getDaysRemaining();
        if (daysRemaining < 0 || daysRemaining === 0) {
            return 'red';
        } else {
            return daysRemaining > 10 ? 'green' : daysRemaining >= 5 ? 'orange' : 'red';
        }
    }

    getDaysRemaining() {
        if (!this.props?.record?.data || !this.props?.name) {
            return null;
        }

        const targetDateStr = this.props.record.data[this.props.name];
        if (!targetDateStr) {
            return null;
        }

        // Normalizar las fechas
        const targetDate = new Date(targetDateStr);
        targetDate.setHours(0, 0, 0, 0);
        const today = new Date();
        today.setHours(0, 0, 0, 0);

        const timeDiff = targetDate - today;
        return Math.floor(timeDiff / (1000 * 60 * 60 * 24));
    }

    shouldDisplayWidget() {
        if (!this.props?.record?.data || !this.props?.name) {
            return false;
        }

        // Verificar si el modelo es 'opportunity' y si el estado cumple las condiciones
        const modelName = this.props.record.model?.config?.resModel;
        const status = this.props.record.data.stage;

        const hiddenStatuses = ["cancelled", "won", "lost"];
        if (modelName === 'opportunity' && hiddenStatuses.includes(status)) {
            return false;
        }

        // Obtener los días restantes
        const daysRemaining = this.getDaysRemaining();

        // Excepción para 'opportunity': mostrar incluso si la fecha ha pasado
        if (modelName === 'opportunity') {
            return daysRemaining !== null; // Mostrar siempre que la fecha sea válida
        }

        // Comportamiento normal para otros modelos
        return daysRemaining !== null && daysRemaining > 0;
    }


}

RemainDaysDatetime.supportedTypes = ['date'];

// Añadir el widget a la categoría de campos
registry.category('fields').add('RemainingDays', { component: RemainDaysDatetime });