frappe.ui.form.on("ToDo", {
	refresh: function (frm) {
			remove_custom_button(frm, [
				__("Reopen"),
				__("Close"),
			]);
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
