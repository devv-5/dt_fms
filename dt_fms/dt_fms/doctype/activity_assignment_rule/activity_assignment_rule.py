# Copyright (c) 2025, DT and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class ActivityAssignmentRule(Document):
	pass


import frappe
from frappe import _

@frappe.whitelist()
def get_fms_active_doctypes():
    try:
        doctypes = frappe.get_all(
            "FMS Settings Doctypes",
            filters={
                "parenttype": "FMS Settings",
                "parent": "FMS Settings"
            },
            fields=["doctype_"]
        )

        # extract non-empty unique values
        unique_doctypes = list({d.doctype_ for d in doctypes if d.doctype_})

        return unique_doctypes

    except Exception as e:
        frappe.throw(_("Unable to fetch active doctypes: {0}").format(str(e)))

