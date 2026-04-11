import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
    filters = frappe._dict(filters or {})
    validate_filters(filters)

    columns = get_columns()
    data = get_data(filters)
    summary = get_summary(data)

    return columns, data, None, None, summary


def validate_filters(filters):
    if not filters.get("from_date"):
        frappe.throw(_("From Date is required."))
    if not filters.get("to_date"):
        frappe.throw(_("To Date is required."))
    if getdate(filters.from_date) > getdate(filters.to_date):
        frappe.throw(_("From Date cannot be after To Date."))


def get_columns():
    return [
        {"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 110},
        {"label": _("POS Closing Entry"), "fieldname": "pos_closing_entry", "fieldtype": "Link", "options": "POS Closing Entry", "width": 190},
        {"label": _("POS Profile"), "fieldname": "pos_profile", "fieldtype": "Link", "options": "POS Profile", "width": 170},
        {"label": _("Business Location"), "fieldname": "business_location", "fieldtype": "Data", "width": 170},
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 170},
        {"label": _("Closed By"), "fieldname": "closed_by", "fieldtype": "Link", "options": "User", "width": 160},
        {"label": _("Expected Amount"), "fieldname": "expected_amount", "fieldtype": "Currency", "width": 145},
        {"label": _("Closing Amount"), "fieldname": "closing_amount", "fieldtype": "Currency", "width": 145},
        {"label": _("Variance"), "fieldname": "variance", "fieldtype": "Currency", "width": 125},
        {"label": _("Shortage"), "fieldname": "shortage", "fieldtype": "Currency", "width": 125},
        {"label": _("Expenses"), "fieldname": "expenses", "fieldtype": "Currency", "width": 125},
        {"label": _("Unmatched Shortage"), "fieldname": "unmatched_shortage", "fieldtype": "Currency", "width": 155},
        {"label": _("Excess Expenses"), "fieldname": "excess_expenses", "fieldtype": "Currency", "width": 145},
        {"label": _("Expense Cost Center"), "fieldname": "expense_cost_center", "fieldtype": "Link", "options": "Cost Center", "width": 190},
        {"label": _("Opening Entry"), "fieldname": "pos_opening_entry", "fieldtype": "Link", "options": "POS Opening Entry", "width": 190},
    ]


def get_data(filters):
    entries = get_closing_entries(filters)
    rows = []

    for entry in entries:
        totals = get_closing_totals(entry.name)
        variance = flt(totals.get("variance"))
        shortage = abs(variance) if variance < 0 else 0
        cost_center = filters.get("cost_center") or get_pos_profile_cost_center(entry.pos_profile)
        expenses = get_expenses(
            posting_date=entry.posting_date,
            company=entry.company,
            cost_center=cost_center,
        )

        rows.append(
            {
                "posting_date": entry.posting_date,
                "pos_closing_entry": entry.name,
                "pos_profile": entry.pos_profile,
                "business_location": get_business_location(entry.pos_profile, cost_center),
                "company": entry.company,
                "closed_by": entry.user,
                "expected_amount": totals.get("expected_amount"),
                "closing_amount": totals.get("closing_amount"),
                "variance": variance,
                "shortage": shortage,
                "expenses": expenses,
                "unmatched_shortage": max(shortage - expenses, 0),
                "excess_expenses": max(expenses - shortage, 0),
                "expense_cost_center": cost_center,
                "pos_opening_entry": entry.pos_opening_entry,
            }
        )

    return rows


def get_closing_entries(filters):
    closing = frappe.qb.DocType("POS Closing Entry")
    opening = frappe.qb.DocType("POS Opening Entry")

    closing_date_field = get_existing_column("POS Closing Entry", ["posting_date", "period_end_date", "closing_date", "modified"])
    user_field = get_existing_column("POS Closing Entry", ["user", "owner"])
    company_field = get_existing_column("POS Closing Entry", ["company"])

    query = (
        frappe.qb.from_(closing)
        .left_join(opening)
        .on(closing.pos_opening_entry == opening.name)
        .select(
            closing.name,
            closing.pos_opening_entry,
            closing[closing_date_field].as_("posting_date"),
            closing[user_field].as_("user"),
            opening.pos_profile,
        )
        .where(closing.docstatus == 1)
        .where(closing[closing_date_field].between(filters.from_date, filters.to_date))
        .orderby(closing[closing_date_field])
        .orderby(closing.name)
    )

    if company_field:
        query = query.select(closing[company_field].as_("company"))
    else:
        query = query.select(opening.company.as_("company"))

    if filters.get("company"):
        if company_field:
            query = query.where(closing[company_field] == filters.company)
        else:
            query = query.where(opening.company == filters.company)

    if filters.get("pos_profile"):
        query = query.where(opening.pos_profile == filters.pos_profile)

    return query.run(as_dict=True)


def get_closing_totals(pos_closing_entry):
    child_table = get_closing_payment_child_table()
    if not child_table:
        return {"expected_amount": 0, "closing_amount": 0, "variance": 0}

    expected_field = get_existing_column(child_table, ["expected_amount", "expected", "system_amount"])
    closing_field = get_existing_column(child_table, ["closing_amount", "counted_amount", "amount"])
    difference_field = get_existing_column(child_table, ["difference", "variance"])

    expected_expr = f"sum(coalesce(`{expected_field}`, 0))" if expected_field else "0"
    closing_expr = f"sum(coalesce(`{closing_field}`, 0))" if closing_field else "0"

    if difference_field:
        variance_expr = f"sum(coalesce(`{difference_field}`, 0))"
    elif expected_field and closing_field:
        variance_expr = f"sum(coalesce(`{closing_field}`, 0) - coalesce(`{expected_field}`, 0))"
    else:
        variance_expr = "0"

    result = frappe.db.sql(
        f"""
        select
            {expected_expr} as expected_amount,
            {closing_expr} as closing_amount,
            {variance_expr} as variance
        from `tab{child_table}`
        where parent = %s
            and parenttype = 'POS Closing Entry'
            and parentfield in ('payment_reconciliation', 'payment_reconciliations')
        """,
        pos_closing_entry,
        as_dict=True,
    )
    return result[0] if result else {"expected_amount": 0, "closing_amount": 0, "variance": 0}


def get_closing_payment_child_table():
    meta = frappe.get_meta("POS Closing Entry")
    for fieldname in ("payment_reconciliation", "payment_reconciliations"):
        df = meta.get_field(fieldname)
        if df and df.options:
            return df.options
    return None


def get_pos_profile_cost_center(pos_profile):
    if not pos_profile or not frappe.db.exists("DocType", "POS Profile"):
        return None

    if frappe.db.has_column("POS Profile", "cost_center"):
        return frappe.db.get_value("POS Profile", pos_profile, "cost_center")

    return None


def get_business_location(pos_profile, cost_center):
    if not pos_profile:
        return cost_center

    values = {"pos_profile": pos_profile, "cost_center": cost_center}
    if frappe.db.has_column("POS Profile", "warehouse"):
        values["warehouse"] = frappe.db.get_value("POS Profile", pos_profile, "warehouse")

    return values.get("warehouse") or values.get("cost_center") or values.get("pos_profile")


def get_expenses(posting_date, company=None, cost_center=None):
    conditions = ["gle.docstatus = 1", "gle.posting_date = %(posting_date)s", "account.root_type = 'Expense'"]
    values = {"posting_date": posting_date}

    if frappe.db.has_column("GL Entry", "is_cancelled"):
        conditions.append("gle.is_cancelled = 0")
    if company:
        conditions.append("gle.company = %(company)s")
        values["company"] = company
    if cost_center and frappe.db.has_column("GL Entry", "cost_center"):
        conditions.append("gle.cost_center = %(cost_center)s")
        values["cost_center"] = cost_center

    result = frappe.db.sql(
        f"""
        select sum(coalesce(gle.debit, 0) - coalesce(gle.credit, 0)) as amount
        from `tabGL Entry` gle
        inner join `tabAccount` account on account.name = gle.account
        where {" and ".join(conditions)}
        """,
        values,
        as_dict=True,
    )
    return flt(result[0].amount if result else 0)


def get_existing_column(doctype, candidates):
    for fieldname in candidates:
        if frappe.db.has_column(doctype, fieldname):
            return fieldname
    return None


def get_summary(data):
    total_shortage = sum(flt(row.get("shortage")) for row in data)
    total_expenses = sum(flt(row.get("expenses")) for row in data)
    total_unmatched = sum(flt(row.get("unmatched_shortage")) for row in data)

    return [
        {"value": total_shortage, "label": _("Total Shortage"), "datatype": "Currency", "indicator": "Red" if total_shortage else "Green"},
        {"value": total_expenses, "label": _("Total Expenses"), "datatype": "Currency", "indicator": "Blue"},
        {"value": total_unmatched, "label": _("Unmatched Shortage"), "datatype": "Currency", "indicator": "Orange" if total_unmatched else "Green"},
    ]
