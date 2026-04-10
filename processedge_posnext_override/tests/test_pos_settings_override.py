from processedge_posnext_override.overrides.sales_invoice import validate_pos_invoice_posting_date


def test_module_imports():
    assert callable(validate_pos_invoice_posting_date)
