# Copyright (c) 2025, DT and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe
from frappe.utils import get_datetime, add_days
from datetime import timedelta


class Checklist(Document):
	def on_submit(doc):
		start = get_datetime(doc.expected_start_time)
		end = get_datetime(doc.expected_end_time)

		for task in doc.tasks:
			if not task.assigned_to:
				continue

			# Generate all schedule points based on frequency
			due_dates = get_due_dates_by_frequency(start, end, task.frequency, task.day_of_week, task.day_of_month)

			for due_date in due_dates:
				frappe.get_doc({
					"doctype": "ToDo",
					"description": create_description(task.subject, task.description),
					"reference_type": "Checklist",
					"reference_name": doc.name,
					"allocated_to": task.assigned_to,
					"status": "Open",
					"priority": "Medium",
					"date": due_date.date(),
					"custom_expected_end_time": due_date,
					"custom_tat_start_time": due_date,
					"assigned_by": doc.assigned_by or frappe.session.user,
				}).insert(ignore_permissions=True)


def create_description(subject, description=None):
	if description:
		return f"{subject}\n{description}"
	else:
		return subject

def get_due_dates_by_frequency(start, end, frequency, day_of_week=None, day_of_month=None):
    dates = []
    current = start

    if frequency == "Daily":
        while current <= end:
            dates.append(current)
            current += timedelta(days=1)

    elif frequency == "Weekly":
        weekday_index = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].index(day_of_week)
        while current <= end:
            if current.weekday() == weekday_index:
                dates.append(current)
                current += timedelta(days=7)
            else:
                current += timedelta(days=1)

    elif frequency == "Monthly":
        while current <= end:
            try:
                monthly_day = int(day_of_month)
                due_date = current.replace(day=monthly_day)
                if start <= due_date <= end:
                    dates.append(due_date)
            except:
                pass
            current = add_days(current, 31)
            current = current.replace(day=1)

    elif frequency == "Custom":
        # You can plug in croniter here for advanced cron parsing if needed
        dates.append(start)  # default fallback

    return dates
