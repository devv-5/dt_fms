import frappe

def execute(filters=None):
    filters = frappe._dict(filters or {})

    columns = [
        {"label": "Task", "fieldname": "name", "fieldtype": "Link", "options": "ToDo", "width": 200},
        {"label": "Subject", "fieldname": "description", "fieldtype": "Data", "width": 300},
        {"label": "Delay Duration", "fieldname": "custom_time_delay", "fieldtype": "Duration", "width": 200},
    ]

    conditions = [
        ["status", "=", "Closed"],
        ["custom_time_delay", ">", 0],
    ]

    if filters.get("user"):
        conditions.append(["allocated_to", "=", filters.user])

    todos = frappe.get_all(
        "ToDo",
        fields=["name", "description", "custom_time_delay", "allocated_to", "custom_closed_by"],
        filters=conditions
    )

    data = []
    for t in todos:
        if t.allocated_to != t.custom_closed_by:
            continue
        data.append({
            "name": t.name,
            "description": t.description,
            "custom_time_delay": t.custom_time_delay
        })

    return columns, data
