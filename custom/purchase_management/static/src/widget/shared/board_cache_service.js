/** @odoo-module **/

import { registry } from "@web/core/registry";


export const boardCacheService = {
    dependencies: ["orm"],
    start(env, { orm }) {
        const cache = new Map();
        const pendingPromises = new Map();
        const CACHE_TTL = 500;
        let cacheTimer = null;

        function clearCache() {
            cache.clear();
            pendingPromises.clear();
        }

        async function getBoardData(recordId, modelName) {
            if (!recordId) return {};

            const cacheKey = `${modelName}_${recordId}`;

            // Si ya está en caché, devolverlo
            if (cache.has(cacheKey)) {
                return cache.get(cacheKey);
            }

            // Si hay una petición en curso para este mismo registro, esperar a esa promesa
            if (pendingPromises.has(cacheKey)) {
                return pendingPromises.get(cacheKey);
            }

            // Si no, crear una nueva petición
            const promise = orm.call(modelName, "get_board_data", [recordId]).then((data) => {
                cache.set(cacheKey, data);
                pendingPromises.delete(cacheKey);

                // Reiniciar el timer de limpieza
                if (cacheTimer) clearTimeout(cacheTimer);
                cacheTimer = setTimeout(clearCache, CACHE_TTL);

                return data;
            }).catch((error) => {
                pendingPromises.delete(cacheKey);
                clearCache();
                throw error;
            });

            pendingPromises.set(cacheKey, promise);
            return promise;
        }

        return {
            getBoardData,
            clearCache,
        };
    },
};

registry.category("services").add("purchase_management.board_cache", boardCacheService);
