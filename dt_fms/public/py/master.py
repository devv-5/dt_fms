import frappe
import dt_fms.public.py.todo_assignment as todo_assignment
import dt_fms.public.py.manual_todo_assignment as manual_todo_assignment
import dt_fms.public.py.activity_assignment_monitor as activity_assignment_monitor


def on_update(doc, method):
    # Call each on_update separately, handle exceptions to avoid blocking
    try:
        todo_assignment.on_update(doc, method)
    except Exception as e:
        frappe.log_error(f"assignment.on_update error: {str(e)}", "Workflow Automation")

    try:
        manual_todo_assignment.on_update(doc, method)
    except Exception as e:
        frappe.log_error(f"manual_todo_assignment.on_update error: {str(e)}", "Manual ToDo Assignment")

    # try:
    #     activity_assignment_monitor.on_update(doc, method)
    # except Exception as e:
    #     frappe.log_error(f"activity_assignment_monitor.on_update error: {str(e)}", "Activity Assignment Monitor")
