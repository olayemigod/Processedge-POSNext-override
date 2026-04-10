import frappe
from frappe import _
from frappe.utils import getdate, nowdate

from processedge_posnext_override.overrides.pos_settings import get_app_settings_doc


def validate_pos_invoice_posting_date(doc, method=None):
    if not getattr(doc, "is_pos", 0):
        return

    settings = get_app_settings_doc()
    posting_date = getattr(doc, "posting_date", None)
    if not posting_date:
        return

    if int(settings.allow_editing_posting_date or 0):
        return

    if getdate(posting_date) != getdate(nowdate()):
        frappe.throw(
            _("Editing Posting Date on POS is disabled in ProcessEdge POSNext Settings."),
            title=_("Posting Date Not Allowed"),
        )
