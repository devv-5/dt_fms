frappe.query_reports["DT User Task Completion Summary"] = {
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
