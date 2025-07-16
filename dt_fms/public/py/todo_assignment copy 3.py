import frappe
from frappe.utils import now, get_datetime, getdate
from datetime import datetime, timedelta, time
from typing import Optional, Dict, List, Set, Union, Tuple
import logging
from functools import lru_cache

# Configure logging
logger = logging.getLogger(__name__)

# Constants
DEFAULT_WORK_START_TIME = time(9, 0, 0)  # 9:00 AM
DEFAULT_WORK_END_TIME = time(18, 0, 0)   # 6:00 PM
MAX_TAT_SECONDS = 30 * 24 * 60 * 60      # 30 days in seconds
DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

class WorkflowAutomationException(Exception):
    """Custom exception for workflow automation errors"""
    pass

def on_update(doc, method: str) -> None:
    """
    Entry point for document updates. Handles workflow state changes.
    
    Args:
        doc: The document being updated
        method: The hook method name (e.g., 'on_update')
    """
    try:
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
    
    Args:
        doc: The document with changed workflow state
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

    # Close todos from previous state
    if previous_state and previous_state != current_state:
        close_previous_state_todos(doc, previous_state, workflow)

    # Create todos for new state
    create_current_state_todos(doc, current_state, workflow)

@lru_cache(maxsize=128)
def get_active_workflow(doctype: str) -> Optional[dict]:
    """
    Get active workflow for doctype with caching
    
    Args:
        doctype: Document type to get workflow for
    
    Returns:
        Workflow document or None if not found
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
        
        return frappe.get_cached_doc("Workflow", workflow[0].name)
    
    except Exception as e:
        logger.error(f"Error fetching workflow for {doctype}: {str(e)}", exc_info=True)
        return None

def create_current_state_todos(doc, current_state: str, workflow) -> None:
    """
    Create todos for users who can transition from current state
    
    Args:
        doc: The document being processed
        current_state: Current workflow state
        workflow: Workflow document
    """
    transitions = get_transitions_with_tat(current_state, workflow)
    if not transitions:
        return

    # Get all unique roles from all transitions
    allowed_roles = get_allowed_roles_from_transitions(transitions)
    if not allowed_roles:
        return

    # Get all users with these roles (optimized single query)
    users = get_users_with_roles(allowed_roles)
    if not users:
        return

    # Batch create todos
    create_todos_for_users(doc, current_state, transitions[0].custom_tat, users)

def get_transitions_with_tat(state: str, workflow) -> List[dict]:
    """
    Get transitions with TAT applicable for given state
    
    Args:
        state: Workflow state to check
        workflow: Workflow document
    
    Returns:
        List of transitions with TAT enabled
    """
    return [
        t for t in workflow.transitions
        if t.state == state and getattr(t, 'custom_tat_applicable', False)
    ]

def get_allowed_roles_from_transitions(transitions: List[dict]) -> Set[str]:
    """
    Extract unique allowed roles from transitions
    
    Args:
        transitions: List of workflow transitions
    
    Returns:
        Set of unique role names
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
    
    Args:
        roles: Set of role names to check
    
    Returns:
        List of user IDs
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

def create_todos_for_users(doc, state: str, tat: int, users: List[str]) -> None:
    """
    Batch create todos for multiple users
    
    Args:
        doc: The reference document
        state: Current workflow state
        tat: Turnaround time in seconds
        users: List of user IDs to assign todos to
    """
    reference_type = doc.doctype
    reference_name = doc.name
    description = (
        f"Please review {reference_type}: {reference_name} "
        f"(Current State: {state})"
    )

    # Validate TAT
    try:
        tat = int(tat)
        if tat <= 0 or tat > MAX_TAT_SECONDS:
            logger.warning(f"Invalid TAT value {tat} for {reference_type} {reference_name}")
            tat = None
    except (TypeError, ValueError):
        logger.warning(f"Invalid TAT value {tat} for {reference_type} {reference_name}")
        tat = None

    todos_to_create = []
    current_time = now()
    assigned_by = frappe.session.user

    for user in users:
        try:
            # Get user-specific working hours and holidays
            working_hours = get_user_working_hours(user)
            holidays = get_holidays_for_user(user)

            # Calculate expected completion time
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

            todos_to_create.append({
                "name": frappe.generate_hash(length=10),
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
                    else None
                )
            })

        except Exception as e:
            logger.error(
                f"Failed to prepare ToDo for user {user} on {reference_type} "
                f"{reference_name}: {str(e)}",
                exc_info=True
            )

    # Batch create todos - corrected bulk_insert usage
    if todos_to_create:
        try:
            # Convert list of dicts to list of tuples for bulk_insert
            # fields = list(todos_to_create[0].keys())
            fields = [
                        "name", "allocated_to", "description", "reference_type",
                        "reference_name", "priority", "assigned_by", "custom_tat",
                        "custom_tat_start_time", "custom_expected_end_time"
                    ]


            values = [tuple(todo[field] for field in fields) for todo in todos_to_create]
            
            
            print(f"\n\n\n\n\nValues = {values}")  # Debugging line to check values
            # return

            frappe.db.bulk_insert(
                "ToDo",
                fields=fields,
                values=values
            )
            logger.info(
                f"Created {len(todos_to_create)} todos for {reference_type} "
                f"{reference_name} in state {state}"
            )
        except Exception as e:
            logger.error(
                f"Failed to create todos for {reference_type} {reference_name}: "
                f"{str(e)}",
                exc_info=True
            )

def close_previous_state_todos(doc, previous_state: str, workflow) -> None:
    """
    Close todos from previous workflow state
    
    Args:
        doc: The document being processed
        previous_state: Previous workflow state
        workflow: Workflow document
    """
    previous_roles = get_roles_for_previous_state(previous_state, workflow)
    if not previous_roles:
        return

    open_todos = get_open_todos_for_doc(doc)
    if not open_todos:
        return

    current_time = now()
    current_user = frappe.session.user

    for todo in open_todos:
        try:
            user_roles = set(frappe.get_roles(todo.allocated_to))
            if not previous_roles.intersection(user_roles):
                continue

            working_hours = get_user_working_hours(todo.allocated_to)
            holidays = get_holidays_for_user(todo.allocated_to)

            time_taken = calculate_actual_working_time(
                start_time=todo.custom_tat_start_time,
                end_time=current_time,
                working_hours_start=working_hours.get("start_time"),
                working_hours_end=working_hours.get("end_time"),
                holidays=holidays
            )

            update_closed_todo(
                todo.name,
                current_time,
                current_user,
                time_taken,
                todo.custom_tat
            )

        except Exception as e:
            logger.error(
                f"Failed to close todo {todo.name} for {doc.doctype} "
                f"{doc.name}: {str(e)}",
                exc_info=True
            )

def get_roles_for_previous_state(state: str, workflow) -> Set[str]:
    """
    Get roles allowed to transition from previous state
    
    Args:
        state: Previous workflow state
        workflow: Workflow document
    
    Returns:
        Set of role names
    """
    transitions = [t for t in workflow.transitions if t.state == state]
    return get_allowed_roles_from_transitions(transitions)

def get_open_todos_for_doc(doc) -> List[dict]:
    """
    Get open todos for a document
    
    Args:
        doc: The document to check todos for
    
    Returns:
        List of open ToDo documents
    """
    try:
        todo_names = frappe.get_all(
            "ToDo",
            filters={
                "reference_type": doc.doctype,
                "reference_name": doc.name,
                "status": "Open"
            },
            pluck="name"
        )
        
        return [frappe.get_cached_doc("ToDo", name) for name in todo_names]
    
    except Exception as e:
        logger.error(
            f"Error fetching todos for {doc.doctype} {doc.name}: {str(e)}",
            exc_info=True
        )
        return []

def update_closed_todo(
    todo_name: str,
    close_time: str,
    closed_by: str,
    time_taken: float,
    tat: Optional[float]
) -> None:
    """
    Update todo with closure information
    
    Args:
        todo_name: Name of ToDo to update
        close_time: When the ToDo was closed
        closed_by: Who closed the ToDo
        time_taken: Actual working time taken (seconds)
        tat: Original TAT (seconds)
    """
    try:
        extra_time = (
            calculate_extra_time_taken(tat, time_taken)
            if tat
            else None
        )

        frappe.db.set_value("ToDo", todo_name, {
            "status": "Closed",
            "custom_tat_close_time": close_time,
            "custom_closed_by": closed_by,
            "custom_time_taken_to_close": time_taken,
            "custom_time_delay": extra_time
        })
        
        logger.info(f"Closed todo {todo_name}")
    
    except Exception as e:
        logger.error(f"Failed to close todo {todo_name}: {str(e)}", exc_info=True)

def calculate_extra_time_taken(tat: float, time_taken: float) -> float:
    """
    Calculate extra time taken compared to TAT
    
    Args:
        tat: Original Turnaround Time (seconds)
        time_taken: Actual time taken (seconds)
    
    Returns:
        Extra time taken (seconds), 0 if within TAT
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

@lru_cache(maxsize=1024)
def get_holidays_for_user(user: str) -> List[datetime.date]:
    """
    Get holiday dates for user with caching
    
    Args:
        user: User ID to check holidays for
    
    Returns:
        List of holiday dates
    """
    holiday_list = None
    try:
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
            holiday_list = emp.get("holiday_list")
            
            # 2. Shift Type's holiday_list
            if not holiday_list and emp.get("default_shift"):
                holiday_list = frappe.get_cached_value(
                    "Shift Type",
                    emp.get("default_shift"),
                    "holiday_list"
                )
            
            # 3. Company's default_holiday_list
            if not holiday_list and emp.get("company"):
                holiday_list = frappe.get_cached_value(
                    "Company",
                    emp.get("company"),
                    "default_holiday_list"
                )

        if not holiday_list:
            return []

        # Fetch holidays from Holiday child table
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

@lru_cache(maxsize=512)
def get_user_working_hours(user: str) -> Dict[str, time]:
    """
    Get user's working hours based on shift with caching
    
    Args:
        user: User ID to check
    
    Returns:
        Dictionary with 'start_time' and 'end_time' or empty dict if not found
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

        shift = frappe.get_cached_doc("Shift Type", emp[0].get("default_shift"))
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
    
    Args:
        start_time: When the timer starts (datetime or ISO format string)
        tat_seconds: Turnaround time in seconds
        working_hours_start: Start of working day (time object)
        working_hours_end: End of working day (time object)
        holidays: List of dates to exclude
    
    Returns:
        Expected datetime of completion or None if invalid input
    """
    try:
        # Input validation and conversion
        if not tat_seconds or tat_seconds <= 0:
            return None

        if isinstance(start_time, str):
            start_time = get_datetime(start_time)

        if not isinstance(start_time, datetime):
            return None

        # Set default working hours if not provided
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
            # Skip holidays
            if holidays and current_time.date() in holidays:
                current_time = datetime.combine(
                    current_time.date() + timedelta(days=1),
                    work_start
                )
                continue

            # Calculate current day's work boundaries
            day_start = datetime.combine(current_time.date(), work_start)
            day_end = datetime.combine(current_time.date(), work_end)

            # Adjust if we started before/after working hours
            if current_time < day_start:
                current_time = day_start
            elif current_time >= day_end:
                current_time = datetime.combine(
                    current_time.date() + timedelta(days=1),
                    work_start
                )
                continue

            # Calculate remaining working time today
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
    
    Args:
        start_time: Start time (datetime or ISO format string)
        end_time: End time (datetime or ISO format string)
        working_hours_start: Start of working day (time object)
        working_hours_end: End of working day (time object)
        holidays: List of dates to exclude
    
    Returns:
        Total working seconds between the timestamps
    """
    try:
        # Convert string inputs to datetime
        if isinstance(start_time, str):
            start_time = get_datetime(start_time)
        if isinstance(end_time, str):
            end_time = get_datetime(end_time)

        if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
            return 0.0

        if end_time <= start_time:
            return 0.0

        # Set default working hours if not provided
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

            # Calculate actual working period for this day
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