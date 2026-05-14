/** @odoo-module **/

const WIDGETS = Object.freeze({
    PRODUCT: "product",
    QUOTATION: "supplier",
});

const PRODUCT_STATES = new Set(["draft"]);

const listeners = new Map();

const widgetState = {
    active: null,
    recordId: null,
    defaultApplied: false,
};

function notifyListeners() {
    for (const [widgetName, callback] of listeners.entries()) {
        try {
            callback(widgetState.active === widgetName);
        } catch (error) {
            console.error("Error notificando al listener del widget", widgetName, error);
        }
    }
}

function applyActiveWidget(widgetName) {
    if (widgetState.active !== widgetName) {
        widgetState.active = widgetName;
        notifyListeners();
    }
}

function computeDefaultWidget(recordState, isNewRecord, options = {}) {
    if (isNewRecord) {
        return WIDGETS.PRODUCT;
    }
    // Nota: La lógica de rechazo principal ahora se maneja en setDefaultWidget para forzar el cambio
    return PRODUCT_STATES.has(recordState) ? WIDGETS.PRODUCT : WIDGETS.QUOTATION;
}

function normalizeRecordId(recordId) {
    return recordId || false;
}

/**
 * Establece el widget por defecto basado en el estado del SDC.
 * Se asegura de que el estado se resetee al navegar entre registros.
 * @param {string} recordState - El estado actual del SDC (ej. 'draft', 'sent').
 * @param {number|false} recordId - El ID del registro actual (false si es nuevo).
 * @param {Object} options - Opciones adicionales (allQuotationRejected, commiteeApprovalRejected).
 */
export function setDefaultWidget(recordState, recordId, options = {}) {
    const normalizedId = normalizeRecordId(recordId);

    if (widgetState.recordId !== normalizedId) {
        widgetState.recordId = normalizedId;
        widgetState.defaultApplied = false;
    }

    // CORRECCIÓN PRINCIPAL:
    // Si hay rechazo, FORZAMOS la vista de producto inmediatamente.
    // Lo hacemos antes de comprobar 'widgetState.defaultApplied' para asegurarnos
    // de que funcione incluso si el usuario ya visitó este registro o si viene de una redirección.
    if (options.allQuotationRejected || options.commiteeApprovalRejected) {
        if (widgetState.active !== WIDGETS.PRODUCT) {
            applyActiveWidget(WIDGETS.PRODUCT);
        }
        // Marcamos como aplicado para mantener la consistencia interna
        widgetState.defaultApplied = true;
        return;
    }

    if (widgetState.defaultApplied) {
        return;
    }

    const defaultWidget = computeDefaultWidget(recordState, normalizedId === false, options);
    applyActiveWidget(defaultWidget);
    widgetState.defaultApplied = true;
}

export function registerWidget(widgetName, callback) {
    // Si no hay estado activo inicial, definimos Product por defecto
    if (widgetState.active === null) {
        widgetState.active = WIDGETS.PRODUCT;
    }

    listeners.set(widgetName, callback);
    callback(widgetState.active === widgetName);

    return () => {
        const storedCallback = listeners.get(widgetName);
        if (storedCallback === callback) {
            listeners.delete(widgetName);
        }
    };
}

export function toggleActiveWidget() {
    const nextWidget =
        widgetState.active === WIDGETS.PRODUCT ? WIDGETS.QUOTATION : WIDGETS.PRODUCT;
    applyActiveWidget(nextWidget);
}

export function getActiveWidget() {
    return widgetState.active;
}

export function setActiveWidget(widgetName) {
    applyActiveWidget(widgetName);
}