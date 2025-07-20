import frappe

def execute(filters=None):
    filters = filters or {}

    columns = [
        {"label": "User", "fieldname": "user", "fieldtype": "Data", "width": 150},
        {"label": "Total Tasks Assigned", "fieldname": "total_assigned", "fieldtype": "Int", "width": 150},
        {"label": "Total Completed", "fieldname": "total_completed", "fieldtype": "Int", "width": 130},
        {"label": "Balance To be Completed", "fieldname": "balance", "fieldtype": "Int", "width": 170},
        {"label": "Completed by User", "fieldname": "completed_by_me", "fieldtype": "Int", "width": 140},
        {"label": "Completed by Other Users", "fieldname": "completed_by_other", "fieldtype": "Int", "width": 150},
    ]

    data = []

    # Construct filter conditions using list-of-lists format
    conditions = [["allocated_to", "!=", ""]]

    if filters.get("user"):
        conditions.append(["allocated_to", "=", filters["user"]])
    if filters.get("from_expected_end_time"):
        conditions.append(["custom_expected_end_time", ">=", filters["from_expected_end_time"]])
    if filters.get("to_expected_end_time"):
        conditions.append(["custom_expected_end_time", "<=", filters["to_expected_end_time"]])

    # Get unique users from filtered ToDos
    users = frappe.get_all(
        "ToDo",
        filters=conditions,
        fields=["DISTINCT allocated_to"]
    )

    for row in users:
        user = row.allocated_to

        # Clone the same conditions and add user-specific filter
        user_conditions = conditions.copy()
        user_conditions.append(["allocated_to", "=", user])

        todos = frappe.get_all(
            "ToDo",
            fields=["name", "status", "allocated_to", "custom_closed_by"],
            filters=user_conditions
        )

        total_assigned = len(todos)
        total_completed = sum(1 for t in todos if t.status == "Closed")
        balance = total_assigned - total_completed

        completed_by_me = sum(1 for t in todos if t.status == "Closed" and t.custom_closed_by == user)
        completed_by_other = sum(1 for t in todos if t.status == "Closed" and t.custom_closed_by and t.custom_closed_by != user)

        data.append({
            "user": user,
            "total_assigned": total_assigned,
            "total_completed": total_completed,
            "balance": balance,
            "completed_by_me": completed_by_me,
            "completed_by_other": completed_by_other,
        })

    return columns, data
