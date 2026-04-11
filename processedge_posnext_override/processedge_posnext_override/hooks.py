"""Compatibility hooks for Frappe Cloud app validation.

The canonical hooks module lives at ``processedge_posnext_override.hooks``.
This shim keeps Frappe Cloud happy when it inspects the nested module folder.
"""

from processedge_posnext_override.hooks import *  # noqa: F401,F403
