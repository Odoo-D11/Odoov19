/** @odoo-module **/

import { Component, onWillStart, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { loadJS } from "@web/core/assets";
import { useService } from "@web/core/utils/hooks";

const ACTION_TAG = "warehouse_dashboard";

export class WarehouseDashboard extends Component {
    static template = "warehouse.WarehouseDashboard";

}

registry.category("actions").add(ACTION_TAG, WarehouseDashboard);
