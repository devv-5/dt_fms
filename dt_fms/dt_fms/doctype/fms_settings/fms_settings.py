# Copyright (c) 2025, DT and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class FMSSettings(Document):
    def before_save(self):
        self.custom_fields_creation()

    def custom_fields_creation(self):
        # Get all doctypes marked active in child table
        active_doctypes = [getattr(d, 'doctype_', None) for d in self.doctypes_to_apply_on if getattr(d, 'active', 0)]
        
        # Fetch all doctypes which ever had these custom fields created
        all_custom_fields = frappe.db.get_all(
            "Custom Field",
            filters={
                "fieldname": ["like", "%dt_fms%"]  # our custom fields identifier pattern
            },
            fields=["name", "dt", "fieldname"]
        )

        # Collect doctypes processed now to avoid deleting their fields
        processed_doctypes = []

        for doctype_value in active_doctypes:
            if not doctype_value:
                continue

            processed_doctypes.append(doctype_value)
            base_fieldname = doctype_value.lower().replace(' ', '_')

            # Fieldnames
            tab_break_fieldname = f"{base_fieldname}_dt_fms_tab_break"
            section_break_fieldname = f"{base_fieldname}_dt_fms_section_break"
            table_fieldname = f"{base_fieldname}_dt_fms_task_assignment"

            # Create Tab Break
            if not frappe.db.exists("Custom Field", {"dt": doctype_value, "fieldname": tab_break_fieldname}):
                last_field = frappe.db.get_value(
                    "DocField",
                    {"parent": doctype_value},
                    "fieldname",
                    order_by="idx desc"
                )

                tab_break_field = frappe.get_doc({
                    "doctype": "Custom Field",
                    "dt": doctype_value,
                    "fieldname": tab_break_fieldname,
                    "label": "FMS Activities",
                    "fieldtype": "Tab Break",
                    "insert_after": last_field or "section_break_0",
                    "hidden": 0
                })
                tab_break_field.insert(ignore_permissions=True)
                # frappe.msgprint(f"Tab Break created in {doctype_value}")

            # Create Section Break
            if not frappe.db.exists("Custom Field", {"dt": doctype_value, "fieldname": section_break_fieldname}):
                section_break_field = frappe.get_doc({
                    "doctype": "Custom Field",
                    "dt": doctype_value,
                    "fieldname": section_break_fieldname,
                    # "label": "Activities Section",
                    "fieldtype": "Section Break",
                    "insert_after": tab_break_fieldname,
                    "hidden": 0
                })
                section_break_field.insert(ignore_permissions=True)
                # frappe.msgprint(f"Section Break created in {doctype_value}")

            # Create Table Field
            if not frappe.db.exists("Custom Field", {"dt": doctype_value, "fieldname": table_fieldname}):
                table_field = frappe.get_doc({
                    "doctype": "Custom Field",
                    "dt": doctype_value,
                    "fieldname": table_fieldname,
                    "label": "Task Assignment",
                    "fieldtype": "Table",
                    "options": "Task Assignment",
                    "insert_after": section_break_fieldname,
                    "hidden": 0
                })
                table_field.insert(ignore_permissions=True)
                # frappe.msgprint(f"Task Assignment Table Field created in {doctype_value}")

        # Now remove custom fields from inactive/removed doctypes
        for cf in all_custom_fields:
            dt = cf["dt"]
            fieldname = cf["fieldname"]

            # If this doctype is not currently active, remove its custom fields
            if dt not in processed_doctypes:
                frappe.delete_doc("Custom Field", cf["name"], ignore_permissions=True)
                # frappe.msgprint(f"Removed Custom Field '{fieldname}' from Doctype '{dt}' as it's no longer active.")

