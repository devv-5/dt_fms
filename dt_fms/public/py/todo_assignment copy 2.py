import frappe
from frappe.utils import now, now_datetime
from datetime import datetime, timedelta, time


def on_update(doc, method):
    send_todo_for_next_state(doc, method)


def get_holidays_for_user(user):
    """
    Get holiday dates for the user by checking Employee, Shift Type, then Company.

    Args:
        user (str): User ID.

    Returns:
        list: List of holiday dates (datetime.date)
    """
    holiday_list = None

    # Get Employee record
    emp = frappe.get_all(
        "Employee",
        filters={"user_id": user},
        fields=["holiday_list", "default_shift", "company"],
        limit=1
    )

    if emp:
        emp = emp[0]
        # 1. Employee's holiday_list
        if emp.get("holiday_list"):
            holiday_list = emp.get("holiday_list")
        else:
            # 2. Shift Type's holiday_list
            if emp.get("default_shift"):
                shift = frappe.get_value("Shift Type", emp.get("default_shift"), "holiday_list")
                if shift:
                    holiday_list = shift

            # 3. Company's default_holiday_list
            if not holiday_list and emp.get("company"):
                company_holiday_list = frappe.get_value("Company", emp.get("company"), "default_holiday_list")
                if company_holiday_list:
                    holiday_list = company_holiday_list

    if not holiday_list:
        return []

    # Fetch holidays from Holiday child table
    holidays = frappe.get_all(
        "Holiday",
        filters={"parent": holiday_list},
        fields=["date"]
    )

    return [h.date for h in holidays if h.date]



def calculate_expected_end_time(start_time, tat_seconds, working_hours_start=None, working_hours_end=None, holidays=None):
    if not tat_seconds:
        return None

    try:
        tat_seconds = int(tat_seconds)
    except (TypeError, ValueError):
        return None

    if isinstance(start_time, str):
        start_time = datetime.strptime(start_time.split('.')[0], "%Y-%m-%d %H:%M:%S")

    work_day_start = datetime.combine(start_time.date(), working_hours_start)
    work_day_end = datetime.combine(start_time.date(), working_hours_end)

    current_time = start_time

    while tat_seconds > 0:
        # Skip holiday dates
        if holidays and current_time.date() in holidays:
            work_day_start += timedelta(days=1)
            work_day_end += timedelta(days=1)
            current_time = work_day_start
            continue

        if current_time < work_day_start:
            current_time = work_day_start
        elif current_time >= work_day_end:
            work_day_start += timedelta(days=1)
            work_day_end += timedelta(days=1)
            current_time = work_day_start
            continue

        remaining_today_seconds = int((work_day_end - current_time).total_seconds())

        if tat_seconds <= remaining_today_seconds:
            return current_time + timedelta(seconds=tat_seconds)
        else:
            tat_seconds -= remaining_today_seconds
            work_day_start += timedelta(days=1)
            work_day_end += timedelta(days=1)
            current_time = work_day_start

    return current_time



def time_to_timedelta(time_str):
    """Convert 'HH:MM:SS' string to timedelta"""
    h, m, s = map(int, time_str.split(":"))
    return timedelta(hours=h, minutes=m, seconds=s)

# Set as timedelta instead of string
DEFAULT_START_TIME = time_to_timedelta("00:00:00")
DEFAULT_END_TIME = time_to_timedelta("23:59:59")

def send_todo_for_next_state(doc, method):
    """
    Handle todo creation and closure based on workflow state changes
    Triggered on validate or on_update of the document
    """
    if not hasattr(doc, 'workflow_state'):
        return

    # Skip if workflow state hasn't changed
    if not doc.has_value_changed('workflow_state'):
        return

    # Get current and previous states
    current_state = doc.get('workflow_state')
    previous_state = doc.get_doc_before_save().get('workflow_state') if doc.get_doc_before_save() else None

    # Get active workflow
    workflow = get_workflow(doc.doctype)
    if not workflow:
        return

    # Close todos from previous state if state changed
    if previous_state and previous_state != current_state:
        close_todos_for_previous_state(doc, previous_state, workflow)

    # Create todos for current state
    create_todos_for_current_state(doc, current_state, workflow)

def get_workflow(doctype):
    """Get active workflow for doctype"""

    workflow = frappe.get_all("Workflow",
        filters={
            "document_type": doctype,
            "is_active": 1
        },
        fields=["name"],
        limit=1
    )
    
    if not workflow:
        frappe.log_error(f"No active workflow found for doctype: {doctype}")
        return None
    
    return frappe.get_doc("Workflow", workflow[0].name)

def create_todos_for_current_state(doc, current_state, workflow):
    """
    Create todos for users who can transition from current state
    """
    # Get transitions for current state
    transitions = [t for t in workflow.transitions if (t.state == current_state and t.custom_tat_applicable)]
    if not transitions:
        return
    
    
    if transitions[0]:
        print("Transition: ",transitions[0])
    tat = transitions[0].custom_tat


    # Get allowed roles from all transitions
    allowed_roles = set()
    for transition in transitions:
        if transition.allowed and transition.custom_tat_applicable:
            allowed_roles.update(role.strip() for role in transition.allowed.split("\n") if role.strip())

    if not allowed_roles:
        return

    # Get users with these roles
    users = frappe.get_all("Has Role",
        filters={
            "role": ["in", list(allowed_roles)],
            "parenttype": "User"
        },
        pluck="parent",
        distinct=True
    )

    if not users:
        return

    # Create todos
    reference_type = doc.doctype
    reference_name = doc.name
    description = f"Please review {reference_type}: {reference_name} (Current State: {current_state})"

    for user in users:
        try:          
             
             # Get user's working hours
            working_hours = get_user_working_hours_from_shift(user)
            start_time = now()
            holidays = get_holidays_for_user(user)
            # Calculate expected end time considering working hours
            expected_end_time = calculate_expected_end_time(
                                start_time=start_time,
                                tat_seconds=tat,
                                working_hours_start=working_hours.get("start_time") if working_hours else None,
                                working_hours_end=working_hours.get("end_time") if working_hours else None,
                                holidays=holidays
                            )

             
            todo = frappe.get_doc({
                "doctype": "ToDo",
                "allocated_to": user,
                "description": description,
                "reference_type": reference_type,
                "reference_name": reference_name,
                "priority": "Medium",
                "date": None,
                "assigned_by": frappe.session.user,
                "custom_tat":tat,
                "custom_tat_start_time":start_time,
                "custom_expected_end_time": expected_end_time.strftime("%Y-%m-%d %H:%M:%S") if expected_end_time else None
            })
            todo.insert()
        except Exception as e:
            frappe.log_error(f"Failed to create ToDo for user {user}: {str(e)}")

def close_todos_for_previous_state(doc, previous_state, workflow):
    """
    Close todos for users who had permission for previous state
    """
    # Find roles allowed to transition FROM previous_state
    previous_transitions = [t for t in workflow.transitions if t.state == previous_state]
    if not previous_transitions:
        return

    previous_allowed_roles = set()
    for transition in previous_transitions:
        if transition.allowed:
            previous_allowed_roles.update(role.strip() for role in transition.allowed.split("\n") if role.strip())

    if not previous_allowed_roles:
        return

    # Get all open ToDos for this document
    todos = frappe.get_all("ToDo",
        filters={
            "reference_type": doc.doctype,
            "reference_name": doc.name,
            "status": "Open"
        },
        fields=["name", "allocated_to"]
    )
    
    current_time = now()
    current_user = frappe.session.user
    
    
    holidays = get_holidays_for_user(current_user)

    for todo in todos:
        todo_doc = frappe.get_doc("ToDo", todo.name)
        
        workinghours = get_user_working_hours_from_shift(user=todo_doc.allocated_to)
        
        user_roles = set(frappe.get_roles(todo.allocated_to))        
        
        time_taken = calculate_todo_close_time_with_respect_to_working_hours(
                        tat_start_time=todo_doc.custom_tat_start_time,
                        tat_end_time=current_time,
                        working_hours_start_time=workinghours.get("start_time") if workinghours else None,
                        working_hours_end_time=workinghours.get("end_time") if workinghours else None,
                        holidays=holidays
                    )
     
        # Check if user had permission for previous state
        if previous_allowed_roles.intersection(user_roles):
            todo_doc.db_set("status", "Closed")
            
            todo_doc.custom_time_taken_to_close = time_taken or 0
            todo_doc.custom_tat_close_time = current_time
            todo_doc.custom_closed_by = current_user
            todo_doc.custom_time_delay = calculate_extra_time_taken(todo_doc.custom_tat or 0,time_taken)
            todo_doc.db_set("custom_closed_by", frappe.session.user)
            
            todo_doc.save(ignore_permissions=True)
            
            
def get_user_working_hours_from_shift(user):
    if not user:
        return None

    emp = frappe.get_all(
        "Employee",
        filters={"user_id": user},
        fields=["default_shift", "name"],
        limit=1
    )

    # Fix the condition to properly check for existence and default_shift
    if not emp or not emp[0]["default_shift"]:
        return None

    emp = emp[0]
    shift = frappe.get_doc("Shift Type", emp["default_shift"])
    start_time = shift.start_time
    end_time = shift.end_time

    return {
        "start_time": start_time,
        "end_time": end_time
    }


def calculate_extra_time_taken(tat, time_taken):
    """Calculate extra time taken for a ToDo."""
    try:
        tat = float(tat) if tat else 0
        time_taken = float(time_taken) if time_taken else 0
    except Exception:
        return 0

    if tat > time_taken:
        return 0
    
    extra = time_taken - tat

def calculate_todo_close_time_with_respect_to_working_hours(
    tat_start_time, 
    tat_end_time,
    working_hours_start_time=None,
    working_hours_end_time=None,
    holidays=None
):
    if not tat_start_time or not tat_end_time:
        return None

    work_start_td = working_hours_start_time if working_hours_start_time else DEFAULT_START_TIME
    work_end_td = working_hours_end_time if working_hours_end_time else DEFAULT_END_TIME

    work_start_time = (datetime.min + work_start_td).time()
    work_end_time = (datetime.min + work_end_td).time()

    if isinstance(tat_start_time, str):
        tat_start_time = datetime.strptime(tat_start_time.split('.')[0], "%Y-%m-%d %H:%M:%S")
    if isinstance(tat_end_time, str):
        tat_end_time = datetime.strptime(tat_end_time.split('.')[0], "%Y-%m-%d %H:%M:%S")

    if tat_end_time < tat_start_time:
        return 0

    total_working_seconds = 0
    current_day = tat_start_time.date()

    while current_day <= tat_end_time.date():
        if holidays and current_day in holidays:
            current_day += timedelta(days=1)
            continue

        work_start_datetime = datetime.combine(current_day, work_start_time)
        work_end_datetime = datetime.combine(current_day, work_end_time)

        actual_start = max(tat_start_time, work_start_datetime) if current_day == tat_start_time.date() else work_start_datetime
        actual_end = min(tat_end_time, work_end_datetime) if current_day == tat_end_time.date() else work_end_datetime

        if actual_start < actual_end:
            total_working_seconds += (actual_end - actual_start).total_seconds()

        current_day += timedelta(days=1)

    return total_working_seconds
