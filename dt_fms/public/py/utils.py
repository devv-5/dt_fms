import frappe
def is_fms_enable():
    """Check if FMS is enabled"""
    return frappe.db.get_value("FMS Settings", "FMS Settings", "enable")

def is_applied_on_doctype(doc):
    """Check if workflow automation is applied on the given doctype"""
    return frappe.db.exists("FMS Settings Doctypes", {
        "parent": "FMS Settings",
        "doctype_": doc.doctype,
        "active": 1
    })
