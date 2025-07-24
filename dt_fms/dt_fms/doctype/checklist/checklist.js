// Copyright (c) 2025, DT and contributors
// For license information, please see license.txt

frappe.ui.form.on("Checklist", {
	onload(frm) {
		if (frm.is_new()){
			frm.set_value("assigned_by", frappe.session.user);
		}
	},
});
