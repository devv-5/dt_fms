frappe.ui.form.on("ToDo", {
	refresh: function (frm) {
		setTimeout(() => {
			frm.remove_custom_button(__("Reopen"));
			frm.remove_custom_button(__("Close"))
		}, 10);
	},
})
