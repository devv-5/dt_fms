import frappe

def execute(filters=None):
    filters = frappe._dict(filters or {})

    columns = [
        {"label": "User", "fieldname": "user", "fieldtype": "Data", "width": 200},
        {"label": "Total Tasks Completed by User", "fieldname": "completed_by_user", "fieldtype": "Int", "width": 220},
        {"label": "Tasks Done on Time", "fieldname": "on_time", "fieldtype": "Int", "width": 180},
        {"label": "Tasks Not Done on Time", "fieldname": "late", "fieldtype": "Int", "width": 180},
    ]

    data = []

    # Base filter for completed tasks
    conditions = [["status", "=", "Closed"]]

    # Apply optional filters
    if filters.get("user"):
        conditions.append(["allocated_to", "=", filters.user])

    if filters.get("from_expected_end_time"):
        conditions.append(["custom_expected_end_time", ">=", filters.from_expected_end_time])

    if filters.get("to_expected_end_time"):
        conditions.append(["custom_expected_end_time", "<=", filters.to_expected_end_time])

    # Fetch filtered ToDos
    todos = frappe.get_all(
        "ToDo",
        fields=[
            "allocated_to", "custom_closed_by", "custom_time_delay",
            "custom_tat_start_time", "custom_expected_end_time"
        ],
        filters=conditions
    )

    user_stats = {}

    for t in todos:
        # Only count if user completed their own task
        if not t.allocated_to or t.custom_closed_by != t.allocated_to:
            continue

        user = t.allocated_to

        if user not in user_stats:
            user_stats[user] = {
                "user": user,
                "completed_by_user": 0,
                "on_time": 0,
                "late": 0
            }

        user_stats[user]["completed_by_user"] += 1

        if t.custom_time_delay is None or t.custom_time_delay == 0:
            user_stats[user]["on_time"] += 1
        else:
            user_stats[user]["late"] += 1

    data = list(user_stats.values())

    return columns, data
