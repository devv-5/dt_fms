import frappe
from frappe.utils import now_datetime, add_to_date, cstr
from dt_fms.public.py.utils import is_applied_on_doctype, is_fms_enable


def on_update(doc, method):
    if not is_fms_enable() or not is_applied_on_doctype(doc):
        return

    rule = get_matching_activity_assignment_rule(doc)
    if not rule:
        return

    tasks = get_all_tasks_of_selected_rule(rule.name)
    if not tasks:
        return

    setattr(doc, "_activity_assignment_handled", True)

    create_task_assignments(doc, tasks)


def get_matching_activity_assignment_rule(doc):
    """Return the first matching rule that satisfies all conditions."""
    rules = frappe.get_all(
        "Activity Assignment Rule",
        filters={
            "document_type": doc.doctype,
            "disable": 0
        },
        order_by="priority desc",
        fields=["name"]
    )

    for r in rules:
        rule = frappe.get_doc("Activity Assignment Rule", r.name)
        if all(evaluate_condition_row(doc, cond) for cond in rule.conditions):
            return rule

    return None


def evaluate_condition_row(doc, cond):
    """
    Evaluate one condition row.
    Requires:
    - cond.field (the fieldname in the target doc)
    - cond.condition (the operator, like '=', '!=', etc.)
    - cond.value (the expected value)
    """
    doc_value = doc.get(cond.field)
    condition_value = cond.value
    operator = cond.condition

    try:
        if operator == "=":
            return doc_value == condition_value
        elif operator == "!=":
            return doc_value != condition_value
        elif operator == ">":
            return float(doc_value) > float(condition_value)
        elif operator == "<":
            return float(doc_value) < float(condition_value)
        elif operator == ">=":
            return float(doc_value) >= float(condition_value)
        elif operator == "<=":
            return float(doc_value) <= float(condition_value)
        elif operator == "in":
            return str(doc_value) in condition_value.split(",")
        elif operator == "not in":
            return str(doc_value) not in condition_value.split(",")
        elif operator == "contains":
            return condition_value in str(doc_value)
    except Exception as e:
        frappe.log_error(f"Condition Eval Error: {e}", "Activity Assignment Rule")
        return False

    return False


def get_all_tasks_of_selected_rule(rule_name):
    return frappe.get_all(
        "Activity Assignment Rule Task",
        filters={"parent": rule_name},
        fields=["name", "subject", "tat", "assignee", "description"]
    )

def create_task_assignments(doc, tasks):
    # Derive the expected child table fieldname
    field_name = f"{frappe.scrub(doc.doctype)}_dt_fms_task_assignment"

    # Validate if the field exists in the DocType
    if not any(df.fieldname == field_name and df.fieldtype == "Table" for df in doc.meta.fields):
        frappe.throw(f"Child table field '{field_name}' not found in {doc.doctype}.")

    for task in tasks:
        expected_start = now_datetime()
        expected_end = add_to_date(expected_start, seconds=task.tat or 0)

        doc.append(field_name, {
            "subject": task.subject,
            "status": "Open",
            "expected_start_time": expected_start,
            "expected_end_time": expected_end,
            "description": task.description,
            "assigned_to": task.assignee
        })
