import frappe
from frappe.utils import now, get_datetime, getdate
from datetime import datetime, timedelta, time
from typing import Optional, Dict, List, Set, Union
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Constants
DEFAULT_WORK_START_TIME = time(9, 0, 0)  # 9:00 AM
DEFAULT_WORK_END_TIME = time(18, 0, 0)   # 6:00 PM
# MAX_TAT_SECONDS = 30 * 24 * 60 * 60      # 30 days in seconds
DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

class WorkflowAutomationException(Exception):
    """Custom exception for workflow automation errors"""
    pass


# def maximum_tat_time(doc):
#     """Calculate the maximum time allowed for a task as per document"""

#     max_tat_list = frappe.db.get_all(
#         "FMS Settings Doctypes",
#         filters={"parent": "FMS Settings", "doctype_": doc.doctype},
#         fields=["maximum_tat"],
#         limit=1
#     )

#     # Check if result exists and extract maximum_tat
#     max_tat = max_tat_list[0].maximum_tat if max_tat_list else None

#     # Fallback to FMS Settings if no specific Doctype setting found
#     if not max_tat:
#         max_tat = frappe.db.get_value("FMS Settings", "FMS Settings", "maximum_tat_time")

#     # Final fallback to default constant
#     max_tat = max_tat if max_tat else MAX_TAT_SECONDS

#     return max_tat


def is_fms_enable():
    """Check if FMS is enabled"""
    return frappe.db.get_value("FMS Settings", "FMS Settings", "enable")

def is_applied_on_doctype(doc):
    """Check if workflow automation is applied on the given doctype"""

    applied_on_doc = frappe.db.get_all("FMS Settings Doctypes",
                                    filters={"parent": "FMS Settings", "doctype_": doc.doctype, "active":1}
                                    )

    return len(applied_on_doc) > 0

def on_update(doc, method: str) -> None:
    """
    Entry point for document updates. Handles workflow state changes.
    """
    try:
        if not is_fms_enable():
            return

        if not is_applied_on_doctype(doc):
            return

        if not hasattr(doc, 'workflow_state'):
            return

        if not doc.has_value_changed('workflow_state'):
            return

        logger.info(
            f"Workflow state changed for {doc.doctype} {doc.name} "
            f"from {doc.get_doc_before_save().get('workflow_state') if doc.get_doc_before_save() else None} "
            f"to {doc.workflow_state}"
        )

        handle_workflow_state_change(doc)

    except Exception as e:
        logger.error(
            f"Failed to process workflow state change for {doc.doctype} {doc.name}: {str(e)}",
            exc_info=True
        )
        raise WorkflowAutomationException(
            f"Workflow automation failed: {str(e)}"
        ) from e



def handle_workflow_state_change(doc) -> None:
    """
    Main handler for workflow state changes
    """
    workflow = get_active_workflow(doc.doctype)
    if not workflow:
        return

    previous_state = (
        doc.get_doc_before_save().get('workflow_state')
        if doc.get_doc_before_save()
        else None
    )
    current_state = doc.get('workflow_state')

    # First close all open todos for this document
    close_all_open_todos_for_doc(doc)

    # Then create todos only for current state
    create_current_state_todos(doc, current_state, workflow)

def get_active_workflow(doctype: str) -> Optional[dict]:
    """
    Get active workflow for doctype
    """
    try:
        workflow = frappe.get_all(
            "Workflow",
            filters={"document_type": doctype, "is_active": 1},
            fields=["name"],
            limit=1
        )

        if not workflow:
            logger.debug(f"No active workflow found for doctype: {doctype}")
            return None

        return frappe.get_doc("Workflow", workflow[0].name)

    except Exception as e:
        logger.error(f"Error fetching workflow for {doctype}: {str(e)}", exc_info=True)
        return None

def close_all_open_todos_for_doc(doc) -> None:
    """
    Close all open todos for a document
    """
    try:
        open_todos = frappe.get_all(
            "ToDo",
            filters={
                "reference_type": doc.doctype,
                "reference_name": doc.name,
                "status": "Open"
            },
            fields=["name", "allocated_to", "custom_tat_start_time", "custom_tat"]
        )

        if not open_todos:
            return

        current_time = now()
        current_user = frappe.session.user

        for todo in open_todos:
            try:
                working_hours = get_user_working_hours(todo.allocated_to)
                holidays = get_holidays_for_user(todo.allocated_to)

                if holidays:
                    print(f"Holidays for {todo.allocated_to}: {holidays}")

                time_taken = calculate_actual_working_time(
                    start_time=todo.custom_tat_start_time,
                    end_time=current_time,
                    working_hours_start=working_hours.get("start_time"),
                    working_hours_end=working_hours.get("end_time"),
                    holidays=holidays
                )

                # print("\n\n\n\n\nTodo Details:")
                # print(f"Name: {todo.name}")
                # print(f"Allocated To: {todo.allocated_to}")
                # print(f"TT = ", time_taken)

                frappe.db.set_value("ToDo", todo.name, {
                    "status": "Closed",
                    "custom_tat_close_time": current_time,
                    "custom_closed_by": current_user,
                    "custom_time_taken_to_close": time_taken,
                    "custom_time_delay": calculate_extra_time_taken(todo.custom_tat, time_taken)
                })

                logger.info(f"Closed todo {todo.name}")

            except Exception as e:
                logger.error(f"Failed to close todo {todo.name}: {str(e)}", exc_info=True)

    except Exception as e:
        logger.error(
            f"Error closing todos for {doc.doctype} {doc.name}: {str(e)}",
            exc_info=True
        )

def create_current_state_todos(doc, current_state: str, workflow) -> None:
    """
    Create todos for users who can transition from current state
    """
    transitions = get_transitions_with_tat(current_state, workflow)
    if not transitions:
        return

    allowed_roles = get_allowed_roles_from_transitions(transitions)
    if not allowed_roles:
        return

    users = get_users_with_roles(allowed_roles)
    if not users:
        return

    reference_type = doc.doctype
    reference_name = doc.name
    description = f"Please review {reference_type}: {reference_name} (Current State: {current_state})"
    current_time = now()
    assigned_by = frappe.session.user

    for user in users:
        try:
            working_hours = get_user_working_hours(user)
            holidays = get_holidays_for_user(user)
            tat = transitions[0].custom_tat

            # Validate TAT
            try:
                tat = int(tat)
                # max_tat_seconds = maximum_tat_time(doc)

                if tat is None or tat <= 0:
                    logger.warning(f"Invalid TAT value {tat} for {reference_type} {reference_name}")
                    tat = None
            except (TypeError, ValueError):
                logger.warning(f"Invalid TAT value {tat} for {reference_type} {reference_name}")
                tat = None

            expected_end_time = (
                calculate_expected_end_time(
                    start_time=current_time,
                    tat_seconds=tat,
                    working_hours_start=working_hours.get("start_time"),
                    working_hours_end=working_hours.get("end_time"),
                    holidays=holidays
                )
                if tat
                else None
            )

            if expected_end_time:
                print("\n\n\n\n\n\n\n\nExpected End Time = ", expected_end_time, "\n\n\n")

            todo = frappe.get_doc({
                "doctype": "ToDo",
                "allocated_to": user,
                "description": description,
                "reference_type": reference_type,
                "reference_name": reference_name,
                "priority": "Medium",
                "assigned_by": assigned_by,
                "custom_tat": tat,
                "custom_tat_start_time": current_time,
                "custom_expected_end_time": (
                    expected_end_time.strftime(DATETIME_FORMAT)
                    if expected_end_time
                    else None)
            })
            todo.insert(ignore_permissions=True)
            logger.info(f"Created todo for user {user} on {reference_type} {reference_name}")

        except Exception as e:
            logger.error(
                f"Failed to create ToDo for user {user} on {reference_type} "
                f"{reference_name}: {str(e)}",
                exc_info=True
            )

def get_transitions_with_tat(state: str, workflow) -> List[dict]:
    """
    Get transitions with TAT applicable for given state
    """
    return [
        t for t in workflow.transitions
        if t.state == state and getattr(t, 'custom_tat_applicable', False)
    ]

def get_allowed_roles_from_transitions(transitions: List[dict]) -> Set[str]:
    """
    Extract unique allowed roles from transitions
    """
    allowed_roles = set()
    for transition in transitions:
        if transition.allowed:
            allowed_roles.update(
                role.strip()
                for role in transition.allowed.split("\n")
                if role.strip()
            )
    return allowed_roles

def get_users_with_roles(roles: Set[str]) -> List[str]:
    """
    Get unique users with any of the specified roles
    """
    try:
        return frappe.get_all(
            "Has Role",
            filters={"role": ["in", list(roles)], "parenttype": "User"},
            pluck="parent",
            distinct=True
        )
    except Exception as e:
        logger.error(f"Error fetching users with roles {roles}: {str(e)}", exc_info=True)
        return []

def calculate_extra_time_taken(tat: float, time_taken: float) -> float:
    """
    Calculate extra time taken compared to TAT
    """
    try:
        tat = float(tat)
        time_taken = float(time_taken)
        return max(0, time_taken - tat)
    except (TypeError, ValueError):
        logger.warning(
            f"Invalid TAT ({tat}) or time_taken ({time_taken}) for extra time calculation"
        )
        return 0

def get_holidays_for_user(user: str) -> List[datetime.date]:
    """
    Get holiday dates for user
    """
    holiday_list = None
    try:
        emp = frappe.get_all(
            "Employee",
            filters={"user_id": user},
            fields=["holiday_list", "default_shift", "company","name"],
            limit=1
        )

        if emp:
            emp = emp[0]
            holiday_list = emp.get("holiday_list")

            if not holiday_list and emp.get("default_shift"):
                holiday_list = frappe.get_value(
                    "Shift Type",
                    emp.get("default_shift"),
                    "holiday_list"
                )

            if not holiday_list and emp.get("company"):
                holiday_list = frappe.get_value(
                    "Company",
                    emp.get("company"),
                    "default_holiday_list"
                )

        if not holiday_list:
            return []



        holidays = frappe.get_all(
            "Holiday",
            filters={"parent": holiday_list},
            fields=["holiday_date"]
        )

        return [
            getdate(h.holiday_date) for h in holidays
            if h.holiday_date
        ]

    except Exception as e:
        logger.error(
            f"Error fetching holidays for user {user}: {str(e)}",
            exc_info=True
        )
        return []

def get_user_working_hours(user: str) -> Dict[str, time]:
    """
    Get user's working hours based on shift
    """
    try:
        emp = frappe.get_all(
            "Employee",
            filters={"user_id": user},
            fields=["default_shift"],
            limit=1
        )

        if not emp or not emp[0].get("default_shift"):
            return {}

        shift = frappe.get_doc("Shift Type", emp[0].get("default_shift"))
        return {
            "start_time": shift.start_time,
            "end_time": shift.end_time
        }

    except Exception as e:
        logger.error(
            f"Error fetching working hours for user {user}: {str(e)}",
            exc_info=True
        )
        return {}

def calculate_expected_end_time(
    start_time: Union[str, datetime],
    tat_seconds: int,
    working_hours_start: Optional[time] = None,
    working_hours_end: Optional[time] = None,
    holidays: Optional[List[datetime.date]] = None
) -> Optional[datetime]:
    """
    Calculate expected end time considering working hours and holidays
    """
    try:
        if not tat_seconds or tat_seconds <= 0:
            return None

        if isinstance(start_time, str):
            start_time = get_datetime(start_time)

        if not isinstance(start_time, datetime):
            return None

        work_start = (
            working_hours_start
            if working_hours_start and isinstance(working_hours_start, time)
            else DEFAULT_WORK_START_TIME
        )
        work_end = (
            working_hours_end
            if working_hours_end and isinstance(working_hours_end, time)
            else DEFAULT_WORK_END_TIME
        )

        if work_end <= work_start:
            logger.warning(
                f"Invalid working hours: end {work_end} <= start {work_start}"
            )
            work_start = DEFAULT_WORK_START_TIME
            work_end = DEFAULT_WORK_END_TIME

        current_time = start_time
        remaining_seconds = tat_seconds

        while remaining_seconds > 0:
            if holidays and current_time.date() in holidays:
                current_time = datetime.combine(
                    current_time.date() + timedelta(days=1),
                    work_start
                )
                continue

            day_start = datetime.combine(current_time.date(), work_start)
            day_end = datetime.combine(current_time.date(), work_end)

            if current_time < day_start:
                current_time = day_start
            elif current_time >= day_end:
                current_time = datetime.combine(
                    current_time.date() + timedelta(days=1),
                    work_start
                )
                continue

            remaining_today = (day_end - current_time).total_seconds()

            if remaining_seconds <= remaining_today:
                return current_time + timedelta(seconds=remaining_seconds)
            else:
                remaining_seconds -= remaining_today
                current_time = datetime.combine(
                    current_time.date() + timedelta(days=1),
                    work_start
                )

        return current_time

    except Exception as e:
        logger.error(
            f"Error calculating expected end time: {str(e)}",
            exc_info=True
        )
        return None

def calculate_actual_working_time(
    start_time: Union[str, datetime],
    end_time: Union[str, datetime],
    working_hours_start: Optional[time] = None,
    working_hours_end: Optional[time] = None,
    holidays: Optional[List[datetime.date]] = None
) -> float:
    """
    Calculate actual working time between two timestamps
    """
    try:
        if isinstance(start_time, str):
            start_time = get_datetime(start_time)
        if isinstance(end_time, str):
            end_time = get_datetime(end_time)

        if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
            return 0.0

        if end_time <= start_time:
            return 0.0

        work_start = (
            working_hours_start
            if working_hours_start and isinstance(working_hours_start, time)
            else DEFAULT_WORK_START_TIME
        )
        work_end = (
            working_hours_end
            if working_hours_end and isinstance(working_hours_end, time)
            else DEFAULT_WORK_END_TIME
        )

        if work_end <= work_start:
            logger.warning(
                f"Invalid working hours: end {work_end} <= start {work_start}"
            )
            work_start = DEFAULT_WORK_START_TIME
            work_end = DEFAULT_WORK_END_TIME

        total_seconds = 0.0
        current_day = start_time.date()

        while current_day <= end_time.date():
            if holidays and current_day in holidays:
                current_day += timedelta(days=1)
                continue

            day_start = datetime.combine(current_day, work_start)
            day_end = datetime.combine(current_day, work_end)

            period_start = max(start_time, day_start)
            period_end = min(end_time, day_end)

            if period_start < period_end:
                total_seconds += (period_end - period_start).total_seconds()

            current_day += timedelta(days=1)

        return total_seconds

    except Exception as e:
        logger.error(
            f"Error calculating actual working time: {str(e)}",
            exc_info=True
        )
        return 0.0
