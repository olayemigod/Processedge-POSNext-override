import frappe
from frappe import _

from processedge_posnext_override.overrides.pos_settings import (
    ensure_posnext_settings_sync,
    get_app_settings_doc,
)


@frappe.whitelist()
def get_pos_override_settings():
    settings = get_app_settings_doc()
    roles = []
    raw_roles = settings.editable_price_roles or ""
    if raw_roles:
        roles = [role.strip() for role in raw_roles.replace("\n", ",").split(",") if role.strip()]
    return {
        "allow_editable_selling_price": int(settings.allow_editable_selling_price or 0),
        "allow_editing_posting_date": int(settings.allow_editing_posting_date or 0),
        "editable_price_roles": roles,
        "posting_date": frappe.utils.nowdate(),
    }


@frappe.whitelist()
def sync_posnext_settings():
    if not frappe.has_permission("System Settings", "write") and "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only a System Manager can sync POSNext settings."))

    ensure_posnext_settings_sync()
    return {"ok": True}
