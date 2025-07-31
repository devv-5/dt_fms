// Copyright (c) 2025, DT and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Activity Assignment Rule", {
// 	refresh(frm) {

// 	},
// });

// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Activity Assignment Rule", {
	setup: function (frm) {
		frm.trigger("set_doctype_query")
	},
	refresh: function (frm) {
		frm.trigger("document_type");
		frm.trigger("get_fms_active_doctype")
	},
	document_type: (frm) => {
		// update the select field options with fieldnames
		if (frm.doc.document_type) {
			frappe.model.with_doctype(frm.doc.document_type, () => {
				let fieldnames = frappe
					.get_meta(frm.doc.document_type)
					.fields.filter((d) => {
						return frappe.model.no_value_type.indexOf(d.fieldtype) === -1;
					})
					.map((d) => {
						return { label: `${d.label} (${d.fieldname})`, value: d.fieldname };
					});
				frm.fields_dict.conditions.grid.update_docfield_property(
					"field",
					"options",
					fieldnames
				);
			});
		}
	},

	set_doctype_query(frm) {
	// First get the allowed doctypes
		frappe.call({
		method: "dt_fms.dt_fms.doctype.activity_assignment_rule.activity_assignment_rule.get_fms_active_doctypes",
		callback: function(r) {
			if (r.message) {
				const doctypes = r.message;

				frm.set_query("document_type", function(doc) {
					return {
						filters: [["name", "in", doctypes]]
					};
				});
			}
		}
	});

	}


});
