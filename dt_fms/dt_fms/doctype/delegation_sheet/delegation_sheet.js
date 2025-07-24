// Copyright (c) 2025, DT and contributors
// For license information, please see license.txt

frappe.ui.form.on("Delegation Sheet", {
	refresh(frm) {
		if (should_show_close_button(frm)) {
			add_close_button(frm);
		}

        frm.set_df_property('expected_end_time_revisions', 'cannot_add_rows', true);
    }
	});

// ---------- Utility Functions ---------- //

function should_show_close_button(frm) {
	return frm.doc.docstatus === 1 && frm.doc.status === "Open";
}

function add_close_button(frm) {
	frm.add_custom_button(__("Close"), () => handle_close_action(frm));
}

function handle_close_action(frm) {
	frappe.call({
		method: "dt_fms.dt_fms.doctype.deligation_sheet.deligation_sheet.close_deligation_sheet",
		args: {
			docname: frm.doc.name
		},
		callback: (r) => {
			if (r.message) {
				frm.reload_doc();
			}
		}
	});
}
