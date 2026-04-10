import frappe
from frappe import _


APP_SETTINGS_DOCTYPE = "ProcessEdge POSNext Settings"


def get_app_settings_doc():
    if frappe.db.exists("DocType", APP_SETTINGS_DOCTYPE):
        try:
            return frappe.get_cached_doc(APP_SETTINGS_DOCTYPE)
        except frappe.DoesNotExistError:
            doc = frappe.get_doc({"doctype": APP_SETTINGS_DOCTYPE})
            doc.insert(ignore_permissions=True)
            return doc

    frappe.throw(_("{0} DocType is not installed yet.").format(APP_SETTINGS_DOCTYPE))


def get_app_flags():
    doc = get_app_settings_doc()
    return {
        "allow_user_to_edit_rate": int(doc.allow_editable_selling_price or 0),
        "allow_change_posting_date": int(doc.allow_editing_posting_date or 0),
    }


def apply_app_settings_to_doc(doc, method=None):
    flags = get_app_flags()
    doc.allow_user_to_edit_rate = flags["allow_user_to_edit_rate"]
    doc.allow_change_posting_date = flags["allow_change_posting_date"]


def ensure_posnext_settings_sync():
    if not frappe.db.exists("DocType", "POS Settings"):
        return

    flags = get_app_flags()
    pos_settings_names = frappe.get_all("POS Settings", pluck="name")

    for name in pos_settings_names:
        current = frappe.db.get_value(
            "POS Settings",
            name,
            ["allow_user_to_edit_rate", "allow_change_posting_date"],
            as_dict=True,
        )
        if not current:
            continue

        updates = {}
        if int(current.allow_user_to_edit_rate or 0) != flags["allow_user_to_edit_rate"]:
            updates["allow_user_to_edit_rate"] = flags["allow_user_to_edit_rate"]
        if int(current.allow_change_posting_date or 0) != flags["allow_change_posting_date"]:
            updates["allow_change_posting_date"] = flags["allow_change_posting_date"]

        if updates:
            frappe.db.set_value("POS Settings", name, updates, update_modified=False)

    frappe.clear_cache(doctype="POS Settings")


def get_pos_settings_override(pos_profile):
    from pos_next.pos_next.doctype.pos_settings.pos_settings import get_pos_settings

    settings = get_pos_settings(pos_profile)
    if not settings:
        settings = {}

    flags = get_app_flags()
    settings["allow_user_to_edit_rate"] = flags["allow_user_to_edit_rate"]
    settings["allow_change_posting_date"] = flags["allow_change_posting_date"]
    return settings
