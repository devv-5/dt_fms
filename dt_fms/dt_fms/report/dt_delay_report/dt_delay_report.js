// Copyright (c) 2025, DT and contributors
// For license information, please see license.txt

frappe.query_reports["DT Delay Report"] = {
	  filters: [
        {
            fieldname: "from_expected_end_time",
            label: "From Expected End Time",
            fieldtype: "Datetime"
        },
        {
            fieldname: "to_expected_end_time",
            label: "To Expected End Time",
            fieldtype: "Datetime"
        },
        {
            fieldname: "user",
            label: "User",
            fieldtype: "Link",
            options: "User"
        }
    ]
};
