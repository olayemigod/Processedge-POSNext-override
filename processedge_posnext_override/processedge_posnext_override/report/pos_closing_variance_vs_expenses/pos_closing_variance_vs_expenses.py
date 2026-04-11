import frappe
from frappe import _
from frappe.utils import flt, get_datetime, getdate


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
        {"label": _("Row ID"), "fieldname": "row_id", "fieldtype": "Data", "hidden": 1},
        {"label": _("Parent Row"), "fieldname": "parent_row", "fieldtype": "Data", "hidden": 1},
        {"label": _("Type"), "fieldname": "row_type", "fieldtype": "Data", "width": 150},
        {"label": _("Source"), "fieldname": "source", "fieldtype": "Data", "width": 180},
        {"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 110},
        {"label": _("Shift Start"), "fieldname": "shift_start", "fieldtype": "Datetime", "width": 160},
        {"label": _("Shift End"), "fieldname": "shift_end", "fieldtype": "Datetime", "width": 160},
        {"label": _("POS Closing Shift"), "fieldname": "pos_closing_shift", "fieldtype": "Link", "options": "POS Closing Shift", "width": 190},
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
        {"label": _("Opening Shift"), "fieldname": "pos_opening_shift", "fieldtype": "Link", "options": "POS Opening Shift", "width": 190},
        {"label": _("Mode of Payment"), "fieldname": "mode_of_payment", "fieldtype": "Link", "options": "Mode of Payment", "width": 170},
        {"label": _("Voucher Type"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 150},
        {"label": _("Voucher"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 190},
        {"label": _("Expense Account"), "fieldname": "expense_account", "fieldtype": "Link", "options": "Account", "width": 220},
        {"label": _("Expense Created At"), "fieldname": "expense_created_at", "fieldtype": "Datetime", "width": 170},
    ]


def get_data(filters):
    entries = get_closing_entries(filters)
    expense_details_by_entry = get_assigned_expense_details(entries, filters)
    rows = []

    for entry in entries:
        totals = get_closing_totals(entry.name)
        variance = flt(totals.get("variance"))
        shortage = abs(variance) if variance < 0 else 0
        cost_center = filters.get("cost_center") or get_pos_profile_cost_center(entry.pos_profile)
        entry_expenses = expense_details_by_entry.get(entry.name, [])
        expenses = sum(flt(expense.get("amount")) for expense in entry_expenses)

        parent_row = f"closing::{entry.name}"
        base_row = {
            "row_id": parent_row,
            "row_type": _("Closing Summary"),
            "source": entry.name,
            "indent": 0,
            "posting_date": entry.posting_date,
            "shift_start": entry.get("shift_start"),
            "shift_end": entry.get("shift_end"),
            "pos_closing_shift": entry.name,
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
            "pos_opening_shift": entry.pos_opening_shift,
        }
        rows.append(base_row)
        rows.extend(get_payment_detail_rows(entry, parent_row))
        rows.extend(
            get_expense_detail_rows(
                entry,
                parent_row,
                cost_center,
                entry_expenses,
            )
        )

    return rows


def get_payment_detail_rows(entry, parent_row):
    rows = []
    for idx, payment in enumerate(get_closing_payment_details(entry.name), start=1):
        variance = flt(payment.get("variance"))
        rows.append(
            {
                "row_id": f"{parent_row}::payment::{idx}",
                "parent_row": parent_row,
                "indent": 1,
                "row_type": _("Variance Source"),
                "source": payment.get("mode_of_payment") or _("Payment Row"),
                "posting_date": entry.posting_date,
                "shift_start": entry.get("shift_start"),
                "shift_end": entry.get("shift_end"),
                "pos_closing_shift": entry.name,
                "pos_profile": entry.pos_profile,
                "company": entry.company,
                "closed_by": entry.user,
                "expected_amount": payment.get("expected_amount"),
                "closing_amount": payment.get("closing_amount"),
                "variance": variance,
                "shortage": abs(variance) if variance < 0 else 0,
                "pos_opening_shift": entry.pos_opening_shift,
                "mode_of_payment": payment.get("mode_of_payment"),
            }
        )

    return rows


def get_expense_detail_rows(entry, parent_row, cost_center, expense_details):
    rows = []
    for idx, expense in enumerate(expense_details, start=1):
        rows.append(
            {
                "row_id": f"{parent_row}::expense::{idx}",
                "parent_row": parent_row,
                "indent": 1,
                "row_type": _("Expense Source"),
                "source": expense.get("voucher_no") or expense.get("account"),
                "posting_date": entry.posting_date,
                "shift_start": entry.get("shift_start"),
                "shift_end": entry.get("shift_end"),
                "pos_closing_shift": entry.name,
                "pos_profile": entry.pos_profile,
                "company": entry.company,
                "expenses": expense.get("amount"),
                "expense_cost_center": expense.get("cost_center") or cost_center,
                "pos_opening_shift": entry.pos_opening_shift,
                "voucher_type": expense.get("voucher_type"),
                "voucher_no": expense.get("voucher_no"),
                "expense_account": expense.get("account"),
                "expense_created_at": expense.get("expense_created_at"),
            }
        )

    return rows


def get_closing_entries(filters):
    closing = frappe.qb.DocType("POS Closing Shift")
    opening = frappe.qb.DocType("POS Opening Shift")

    closing_date_field = get_existing_column("POS Closing Shift", ["posting_date", "period_end_date", "closing_date", "modified"])
    user_field = get_existing_column("POS Closing Shift", ["user", "owner"])
    company_field = get_existing_column("POS Closing Shift", ["company"])
    shift_start_field = get_existing_column("POS Closing Shift", ["period_start_date"])
    shift_end_field = get_existing_column("POS Closing Shift", ["period_end_date"])

    query = (
        frappe.qb.from_(closing)
        .left_join(opening)
        .on(closing.pos_opening_shift == opening.name)
        .select(
            closing.name,
            closing.pos_opening_shift,
            closing[closing_date_field].as_("posting_date"),
            closing[user_field].as_("user"),
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

    if frappe.db.has_column("POS Closing Shift", "pos_profile"):
        query = query.select(closing.pos_profile)
    else:
        query = query.select(opening.pos_profile)

    if shift_start_field:
        query = query.select(closing[shift_start_field].as_("shift_start"))
    else:
        query = query.select(opening.period_start_date.as_("shift_start"))

    if shift_end_field:
        query = query.select(closing[shift_end_field].as_("shift_end"))
    else:
        query = query.select(opening.period_end_date.as_("shift_end"))

    if filters.get("company"):
        if company_field:
            query = query.where(closing[company_field] == filters.company)
        else:
            query = query.where(opening.company == filters.company)

    if filters.get("pos_profile"):
        if frappe.db.has_column("POS Closing Shift", "pos_profile"):
            query = query.where(closing.pos_profile == filters.pos_profile)
        else:
            query = query.where(opening.pos_profile == filters.pos_profile)

    return query.run(as_dict=True)


def get_assigned_expense_details(entries, filters):
    grouped_entries = {}
    assigned = {entry.name: [] for entry in entries}

    for entry in entries:
        cost_center = filters.get("cost_center") or get_pos_profile_cost_center(entry.pos_profile)
        key = (str(entry.posting_date), entry.company, cost_center)
        grouped_entries.setdefault(key, []).append(entry)

    for (posting_date, company, cost_center), shift_entries in grouped_entries.items():
        shift_entries = sorted(
            shift_entries,
            key=lambda entry: (
                get_datetime(entry.get("shift_start")) or get_datetime(entry.posting_date),
                get_datetime(entry.get("shift_end")) or get_datetime(entry.posting_date),
                entry.name,
            ),
        )
        expense_details = get_expense_details(
            posting_date=posting_date,
            company=company,
            cost_center=cost_center,
            include_cogs=filters.get("include_cogs"),
        )

        for expense in expense_details:
            entry = get_expense_shift(expense, shift_entries)
            if entry:
                assigned.setdefault(entry.name, []).append(expense)

    return assigned


def get_expense_shift(expense, shift_entries):
    if not shift_entries:
        return None

    expense_created_at = get_datetime(expense.get("expense_created_at"))
    if not expense_created_at:
        return shift_entries[-1]

    for entry in shift_entries:
        shift_start = get_datetime(entry.get("shift_start"))
        shift_end = get_datetime(entry.get("shift_end"))
        if shift_start and shift_end and shift_start <= expense_created_at <= shift_end:
            return entry

    return min(
        shift_entries,
        key=lambda entry: abs((get_shift_reference_time(entry) - expense_created_at).total_seconds()),
    )


def get_shift_reference_time(entry):
    return (
        get_datetime(entry.get("shift_end"))
        or get_datetime(entry.get("shift_start"))
        or get_datetime(entry.posting_date)
    )


def get_closing_totals(pos_closing_shift):
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
            and parenttype = 'POS Closing Shift'
            and parentfield in ('payment_reconciliation', 'payment_reconciliations')
        """,
        pos_closing_shift,
        as_dict=True,
    )
    return result[0] if result else {"expected_amount": 0, "closing_amount": 0, "variance": 0}


def get_closing_payment_details(pos_closing_shift):
    child_table = get_closing_payment_child_table()
    if not child_table:
        return []

    mode_field = get_existing_column(child_table, ["mode_of_payment", "payment_method", "payment_type"])
    expected_field = get_existing_column(child_table, ["expected_amount", "expected", "system_amount"])
    closing_field = get_existing_column(child_table, ["closing_amount", "counted_amount", "amount"])
    difference_field = get_existing_column(child_table, ["difference", "variance"])

    select_fields = ["idx"]
    select_fields.append(f"`{mode_field}` as mode_of_payment" if mode_field else "'' as mode_of_payment")
    select_fields.append(f"coalesce(`{expected_field}`, 0) as expected_amount" if expected_field else "0 as expected_amount")
    select_fields.append(f"coalesce(`{closing_field}`, 0) as closing_amount" if closing_field else "0 as closing_amount")

    if difference_field:
        select_fields.append(f"coalesce(`{difference_field}`, 0) as variance")
    elif expected_field and closing_field:
        select_fields.append(f"coalesce(`{closing_field}`, 0) - coalesce(`{expected_field}`, 0) as variance")
    else:
        select_fields.append("0 as variance")

    return frappe.db.sql(
        f"""
        select {", ".join(select_fields)}
        from `tab{child_table}`
        where parent = %s
            and parenttype = 'POS Closing Shift'
            and parentfield in ('payment_reconciliation', 'payment_reconciliations')
        order by idx
        """,
        pos_closing_shift,
        as_dict=True,
    )


def get_closing_payment_child_table():
    meta = frappe.get_meta("POS Closing Shift")
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


def get_expenses(posting_date, company=None, cost_center=None, include_cogs=False):
    conditions = get_expense_conditions(include_cogs=include_cogs)
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


def get_expense_details(
    posting_date,
    company=None,
    cost_center=None,
    include_cogs=False,
):
    conditions = get_expense_conditions(include_cogs=include_cogs)
    values = {"posting_date": posting_date}

    if frappe.db.has_column("GL Entry", "is_cancelled"):
        conditions.append("gle.is_cancelled = 0")
    if company:
        conditions.append("gle.company = %(company)s")
        values["company"] = company
    if cost_center and frappe.db.has_column("GL Entry", "cost_center"):
        conditions.append("gle.cost_center = %(cost_center)s")
        values["cost_center"] = cost_center

    return frappe.db.sql(
        f"""
        select
            gle.voucher_type,
            gle.voucher_no,
            gle.account,
            gle.cost_center,
            min(gle.creation) as expense_created_at,
            sum(coalesce(gle.debit, 0) - coalesce(gle.credit, 0)) as amount
        from `tabGL Entry` gle
        inner join `tabAccount` account on account.name = gle.account
        where {" and ".join(conditions)}
        group by gle.voucher_type, gle.voucher_no, gle.account, gle.cost_center
        having amount != 0
        order by gle.voucher_type, gle.voucher_no, gle.account
        """,
        values,
        as_dict=True,
    )


def get_expense_conditions(include_cogs=False):
    conditions = [
        "gle.docstatus = 1",
        "gle.posting_date = %(posting_date)s",
        "account.root_type = 'Expense'",
    ]

    if not include_cogs:
        conditions.append(
            """
            coalesce(account.account_type, '') not in (
                'Cost of Goods Sold',
                'Stock Adjustment',
                'Expenses Included In Valuation',
                'Expenses Included In Asset Valuation'
            )
            """
        )

    return conditions


def get_existing_column(doctype, candidates):
    for fieldname in candidates:
        if frappe.db.has_column(doctype, fieldname):
            return fieldname
    return None


def get_summary(data):
    summary_rows = [row for row in data if not row.get("parent_row")]
    total_shortage = sum(flt(row.get("shortage")) for row in summary_rows)
    total_expenses = sum(flt(row.get("expenses")) for row in summary_rows)
    total_unmatched = sum(flt(row.get("unmatched_shortage")) for row in summary_rows)

    return [
        {"value": total_shortage, "label": _("Total Shortage"), "datatype": "Currency", "indicator": "Red" if total_shortage else "Green"},
        {"value": total_expenses, "label": _("Total Expenses"), "datatype": "Currency", "indicator": "Blue"},
        {"value": total_unmatched, "label": _("Unmatched Shortage"), "datatype": "Currency", "indicator": "Orange" if total_unmatched else "Green"},
    ]
