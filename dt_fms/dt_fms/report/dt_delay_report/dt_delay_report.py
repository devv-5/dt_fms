import frappe

def execute(filters=None):
    filters = frappe._dict(filters or {})

    columns = [
        {"label": "User", "fieldname": "user", "fieldtype": "Data", "width": 200},
        {"label": "No. of Tasks Delayed", "fieldname": "delayed_tasks", "fieldtype": "Int", "width": 180},
        {"label": "Total Delayed", "fieldname": "total_delay", "fieldtype": "Duration", "width": 180},
        {"label": "Average Delay", "fieldname": "avg_delay", "fieldtype": "Duration", "width": 200},
    ]

    # Prepare filters
    conditions = [
        ["status", "=", "Closed"],
        ["custom_time_delay", ">", 0],
    ]

    if filters.get("user"):
        conditions.append(["allocated_to", "=", filters.user])
    if filters.get("from_expected_end_time"):
        conditions.append(["custom_expected_end_time", ">=", filters.from_expected_end_time])
    if filters.get("to_expected_end_time"):
        conditions.append(["custom_expected_end_time", "<=", filters.to_expected_end_time])

    # Fetch ToDos with delay
    todos = frappe.get_all(
        "ToDo",
        fields=["allocated_to", "custom_time_delay","custom_closed_by"],
        filters=conditions
    )

    user_stats = {}

    for t in todos:
        if not t.allocated_to or t.custom_closed_by != t.allocated_to:
            continue
        user = t.allocated_to
        if not user:
            continue

        delay = t.custom_time_delay or 0

        if user not in user_stats:
            user_stats[user] = {
                "user": user,
                "delayed_tasks": 0,
                "total_delay": 0.0,
            }

        user_stats[user]["delayed_tasks"] += 1
        user_stats[user]["total_delay"] += float(delay)

    # Calculate average
    for stats in user_stats.values():
        if stats["delayed_tasks"] > 0:
            stats["avg_delay"] = round(stats["total_delay"] / stats["delayed_tasks"], 2)
        else:
            stats["avg_delay"] = 0.0

    return columns, list(user_stats.values())
