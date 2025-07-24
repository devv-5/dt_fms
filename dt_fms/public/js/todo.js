frappe.ui.form.on("ToDo", {
	refresh: function (frm) {

		if (!(frm.doc.reference_type === "Checklist")) {
			remove_custom_button(frm, [
				__("Reopen"),
				__("Close"),
			]);
		}
		remove_custom_button(frm,__("Reopen"));
	},
})


function remove_custom_button(frm, labels) {
	if (!Array.isArray(labels)) {
		labels = [labels];
	}
	labels.forEach(function (label) {
		frm.remove_custom_button(label);
	});

}
