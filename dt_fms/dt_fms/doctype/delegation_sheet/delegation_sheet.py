import frappe
import frappe
from frappe.utils import get_datetime, now_datetime
from datetime import datetime, timedelta, time
import pytz

from frappe.model.document import Document


class DelegationSheet(Document):
	def validate(self):
		self.set_tat()
		self.set_delegator()

	def on_submit(self):
		self.create_todo()


	def on_cancel(self):
		self.cancel_todo()

	def on_update_after_submit(self):
		# Get previous version of the document before the update
		old_doc = self.get_doc_before_save()

		if not old_doc:
			return

		old_end_time = get_datetime(old_doc.revision_expected_end_time)
		new_end_time = get_datetime(self.revision_expected_end_time)

		if old_end_time != new_end_time:
			self.create_item_in_revision_child_table(old_end_time, new_end_time)
			self.db_set("expected_end_time", new_end_time)
			self.set_db_tat()
			self.cancel_todo()
			self.create_todo()
			self.reload()

	def cancel_todo(self):
		todos = frappe.get_all(
			"ToDo",
			filters={
				"reference_type": self.doctype,
				"reference_name": self.name,
			},
			fields=["name"]
		)

		for todo in todos:
			todo_doc = frappe.get_doc("ToDo", todo.name)
			if todo_doc.status != "Closed":
				todo_doc.status = "Cancelled"
				todo_doc.save()

	def create_item_in_revision_child_table(self, old, new):
		"""Insert a child row in DB for submitted document"""
		frappe.get_doc({
			"doctype": "Delegation Sheet Revisions",
			"parent": self.name,
			"parenttype": "Delegation Sheet",
			"parentfield": "expected_end_time_revisions",
			"revisoin_from": old,
			"revision_to": new,
			"revision_on": now_datetime(),
			"revision_by": frappe.session.user
		}).insert(ignore_permissions=True)





	def set_delegator(self):
		"""
		Set the delegator to the current user if not already set.
		This is useful for cases where the delegator is not explicitly set.
		"""
		if not self.delegator:
			self.delegator = frappe.session.user


	def create_todo(self):
		"""
		Create a Todo based on the Deligation Sheet on Submit.
		"""
		if not self.delegatee:
			frappe.throw("Delegatee is required to create a Todo.")

		todo = frappe.get_doc({
			"doctype": "ToDo",
			"description": self.create_todo_description(),
			"reference_type": self.doctype,
			"reference_name": self.name,
			"custom_tat_start_time": self.expected_start_time,
			"custom_expected_end_time": self.expected_end_time,
			"custom_tat": self.tat,
			"status": "Open",
   			"priority": self.priority,
			"assigned_by":self.delegator,
			"allocated_to": self.delegatee,
		})
		todo.insert()


	def create_todo_description(self):
		return f"{self.subject}\n{self.description or ''}".strip()

	def set_tat(self):
		self.tat = get_tat(self.expected_start_time, self.expected_end_time, self.delegatee)

	def set_db_tat(self):
		"""
		Set the TAT in the database.
		This is useful for cases where the TAT needs to be updated after creation.
		"""
		self.db_set("tat", get_tat(self.expected_start_time, self.expected_end_time, self.delegatee))



	def cancel_todo(self):
		todos = frappe.get_all(
			"ToDo",
			filters={
				"reference_type": self.doctype,
				"reference_name": self.name,
			},
			fields=["name"]
		)


		for todo in todos:
			todo_doc = frappe.get_doc("ToDo", todo.name)
			if todo_doc.status != "Closed":
				todo_doc.status = "Cancelled"
				todo_doc.save()
			else:
				frappe.throw(f"Todo {todo.name} is already closed and cannot be cancelled.")



@frappe.whitelist()
def close_delegation_sheet(docname = None):
	"""
	Close the Deligation Sheet and update the associated Todo.
	"""
	if not docname:
		frappe.throw("Document name is required to close the Deligation Sheet.")

	doc = frappe.get_doc("Deligation Sheet", docname)
	if doc.status != "Open":
		frappe.throw(f"Deligation Sheet {docname} is not in Open status.")

	doc.status = "Closed"
	doc.save()

	todos = frappe.get_all(
		"ToDo",
		filters={
			"reference_type": "Deligation Sheet",
			"reference_name": docname,
			"status": "Open"
		},
		fields=["name"]
	)

	for todo in todos:
		todo_doc = frappe.get_doc("ToDo", todo.name)
		todo_doc.status = "Closed"
		todo_doc.custom_tat_close_time = get_datetime()
		todo_doc.custom_closed_by = todo_doc.allocated_to
		todo_doc.custom_time_taken_to_close = get_tat(
			todo_doc.custom_tat_start_time,
			todo_doc.custom_tat_close_time,
			todo_doc.allocated_to
		)

		todo_doc.custom_time_delay = (
			todo_doc.custom_time_taken_to_close -
			todo_doc.custom_tat
		) if todo_doc.custom_time_taken_to_close and todo_doc.custom_tat else None
		todo_doc.save()








def to_time(val):
    if isinstance(val, timedelta):
        total_seconds = int(val.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return time(hour=hours, minute=minutes, second=seconds)
    elif isinstance(val, time):
        return val
    return time(0, 0, 0)

def get_tat( start, end, assigned_to):
    """
    Calculate the Turnaround Time (TAT) in seconds, considering shift timings and holidays.
    Handles timezone-aware and timedelta shift durations (Frappe v15 compatible).
    """
    if not start or not end:
        print("\n\n\n\n[DEBUG] Missing expected_start_time or expected_end_time\n\n")
        return 0

    system_timezone_str = frappe.utils.get_system_timezone()
    system_tz = pytz.timezone(system_timezone_str)
    print(f"\n\n\n\n[DEBUG] System timezone: {system_timezone_str}\n\n")

    expected_start = get_datetime(start)
    expected_end = get_datetime(end)
    print(f"\n\n\n\n[DEBUG] Raw expected_start: {expected_start}, expected_end: {expected_end}\n\n")

    if expected_start.tzinfo is None:
        expected_start = system_tz.localize(expected_start)
    else:
        expected_start = expected_start.astimezone(system_tz)

    if expected_end.tzinfo is None:
        expected_end = system_tz.localize(expected_end)
    else:
        expected_end = expected_end.astimezone(system_tz)

    print(f"\n\n\n\n[DEBUG] Timezone-aware expected_start: {expected_start}, expected_end: {expected_end}\n\n")

    if expected_start >= expected_end:
        print("\n\n\n\n[DEBUG] Start time is after or equal to end time. Returning 0.\n\n")
        return 0

    user_id = assigned_to
    employee = frappe.db.get_value(
        "Employee", {"user_id": user_id},
        ["default_shift", "holiday_list"], as_dict=True
    )
    print(f"\n\n\n\n[DEBUG] Employee for user {user_id}: {employee}\n\n")

    shift_start_time = time(0, 0, 0)
    shift_end_time = time(23, 59, 59)
    holidays = set()

    if employee:
        if employee.default_shift:
            shift = frappe.get_doc("Shift Type", employee.default_shift)
            shift_start_time = to_time(shift.start_time) or shift_start_time
            shift_end_time = to_time(shift.end_time) or shift_end_time
            print(f"\n\n\n\n[DEBUG] Shift timings from '{employee.default_shift}': {shift_start_time} - {shift_end_time}\n\n")

        if employee.holiday_list:
            holiday_dates = frappe.db.get_all(
                "Holiday",
                filters={"parent": employee.holiday_list},
                pluck="holiday_date"
            )
            holidays = set(holiday_dates)
            print(f"\n\n\n\n[DEBUG] Holidays from list '{employee.holiday_list}': {holidays}\n\n")

    total_seconds = 0
    current_dt = expected_start

    print(f"\n\n\n\n[DEBUG] Starting TAT calculation loop from {current_dt} to {expected_end}\n\n")

    while current_dt < expected_end:
        print(f"\n\n\n\n[DEBUG] Checking date: {current_dt.date()}\n\n")

        if current_dt.date() not in holidays:
            naive_shift_start = datetime.combine(current_dt.date(), shift_start_time)
            naive_shift_end = datetime.combine(current_dt.date(), shift_end_time)

            shift_start_dt = system_tz.localize(naive_shift_start)
            shift_end_dt = system_tz.localize(naive_shift_end)

            day_start = max(expected_start, shift_start_dt)
            day_end = min(expected_end, shift_end_dt)

            print(f"\n\n\n\n[DEBUG] Shift window for {current_dt.date()}: {shift_start_dt} - {shift_end_dt}\n[DEBUG] Overlap: {day_start} - {day_end}\n\n")

            if day_start < day_end:
                seconds = (day_end - day_start).total_seconds()
                total_seconds += seconds
                print(f"\n\n\n\n[DEBUG] Added {seconds} seconds for {current_dt.date()}, total now {total_seconds}\n\n")
        else:
            print(f"\n\n\n\n[DEBUG] Skipping holiday: {current_dt.date()}\n\n")

        current_dt += timedelta(days=1)

    print(f"\n\n\n\n[DEBUG] Final total_seconds: {total_seconds}\n\n")
    return int(total_seconds)

