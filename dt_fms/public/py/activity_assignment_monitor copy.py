import frappe
from dt_fms.public.py.utils import is_applied_on_doctype, is_fms_enable

def on_update(doc, method):
    if not is_fms_enable() or not is_applied_on_doctype(doc):
        return

    rules = get_matching_activity_assignment_rules(doc)
    r = ""
    for rule in rules:
        r = rule
        break

    if not r:
        return

    tasks = get_all_task_of_selected_rule(r.name)



def create_task_assignment(doc,tasks):
    for task in tasks:
        doc = frappe.new_doc('Task Assignment')
        doc.parent = doc.name,
        doc.parenttype = doc.doctype,
        doc.subject = task.subject
        doc.status = "Open"
        doc.expected_start_time = ""#Currenct time
        doc.expected_end_time = ""#Current time + task.tat
        doc.description = task.description
        doc.assigned_to = task.assignee
        doc.insert()

def get_all_task_of_selected_rule(rule):
    tasks = frappe.get_all(
		"Activity Assignment Rule Task",
  		filters={"parent": rule},
		fields=["name", "subject", "tat", "assignee","description"]
	)

def get_matching_activity_assignment_rules(doc):
    """Fetch all active rules for the doc.doctype and check conditions."""
    rules = frappe.get_all(
        "Activity Assignment Rule",
        filters={
            "document_type": doc.doctype,
            "disable": 0
        },
        order_by="priority desc",
        fields=["name"]
    )

    matched_rules = []
    for r in rules:
        rule = frappe.get_doc("Activity Assignment Rule", r.name)
        if all(evaluate_condition_row(doc, cond) for cond in rule.conditions):
            matched_rules.append(rule)

    return matched_rules[0]

def evaluate_condition_row(doc, cond):
    """
    Evaluate one row in the 'conditions' table.
    Example fields in `cond` might be:
    - fieldname: status
    - operator: "="
    - value: Draft
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
            return doc_value in condition_value.split(",")
        elif operator == "not in":
            return doc_value not in condition_value.split(",")
        elif operator == "contains":
            return condition_value in str(doc_value)
    except Exception as e:
        frappe.log_error(f"Error evaluating condition: {e}", "Activity Assignment Rule")
        return False

    return False
