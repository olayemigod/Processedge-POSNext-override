import frappe
from frappe import _

from processedge_posnext_override.overrides.pos_settings import (
    ensure_posnext_settings_sync,
    get_current_pos_profile,
    get_effective_rate_editability,
    get_app_settings_doc,
)


@frappe.whitelist()
def get_pos_override_settings(pos_profile=None):
    settings = get_app_settings_doc()
    roles = []
    raw_roles = settings.editable_price_roles or ""
    if raw_roles:
        roles = [role.strip() for role in raw_roles.replace("\n", ",").split(",") if role.strip()]
    pos_profile = pos_profile or get_current_pos_profile()
    return {
        "allow_editable_selling_price": int(get_effective_rate_editability(pos_profile=pos_profile)),
        "allow_editing_posting_date": int(settings.allow_editing_posting_date or 0),
        "editable_price_roles": roles,
        "pos_profile": pos_profile,
        "posting_date": frappe.utils.nowdate(),
    }


@frappe.whitelist()
def sync_posnext_settings():
    if not frappe.has_permission("System Settings", "write") and "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only a System Manager can sync POSNext settings."))

    ensure_posnext_settings_sync()
    return {"ok": True}
