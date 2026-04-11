frappe.query_reports["POS Closing Variance vs Expenses"] = {
  tree: true,
  name_field: "row_id",
  parent_field: "parent_row",
  initial_depth: 1,
  filters: [
    {
      fieldname: "from_date",
      label: __("From Date"),
      fieldtype: "Date",
      default: frappe.datetime.month_start(),
      reqd: 1,
    },
    {
      fieldname: "to_date",
      label: __("To Date"),
      fieldtype: "Date",
      default: frappe.datetime.get_today(),
      reqd: 1,
    },
    {
      fieldname: "company",
      label: __("Company"),
      fieldtype: "Link",
      options: "Company",
    },
    {
      fieldname: "pos_profile",
      label: __("POS Profile"),
      fieldtype: "Link",
      options: "POS Profile",
    },
    {
      fieldname: "cost_center",
      label: __("Expense Cost Center"),
      fieldtype: "Link",
      options: "Cost Center",
      description: __("Optional. If blank, the report uses the POS Profile cost center when available."),
    },
  ],
};
