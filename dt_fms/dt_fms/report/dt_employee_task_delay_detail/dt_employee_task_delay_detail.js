// Copyright (c) 2025, DT and contributors
// For license information, please see license.txt

frappe.query_reports["DT Employee Task Delay Detail"] = {
    filters: [
        {
            fieldname: "user",
            label: "User",
            fieldtype: "Link",
            options: "User",
            reqd: 0
        }
    ]
};
