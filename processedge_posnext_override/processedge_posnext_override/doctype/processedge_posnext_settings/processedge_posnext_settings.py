import frappe
from frappe.model.document import Document

from processedge_posnext_override.overrides.pos_settings import ensure_posnext_settings_sync


class ProcessEdgePOSNextSettings(Document):
    def validate(self):
        self.editable_price_roles = (self.editable_price_roles or "").strip()

    def on_update(self):
        ensure_posnext_settings_sync()
