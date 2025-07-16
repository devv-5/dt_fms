frappe.ui.form.on('Task Assignment', {
    assigned_users(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        render_assigned_to_input(row, cdt, cdn);
    },

    assigned_to_html(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        render_assigned_to_input(row, cdt, cdn);
    },

    form_render(frm, cdt, cdn) {
		console.log("Hello workd")
        const row = locals[cdt][cdn];
        render_assigned_to_input(row, cdt, cdn);
    }
});

function render_assigned_to_input(row, cdt, cdn) {
    frappe.after_ajax(() => {
        const field = frappe.meta.get_docfield(cdt, 'assigned_to_html', cdn);
        if (!field || !field.$wrapper) return;

        const wrapper = field.$wrapper;
        wrapper.empty();

        const current_users = (row.assigned_users || "")
            .split(",")
            .map(u => u.trim())
            .filter(Boolean);

        const html = `
            <div>
                <input type="text" id="assigned_to_input_${cdn}" placeholder="Enter comma-separated users" class="form-control mb-2">
                <div id="assigned_to_badges_${cdn}" style="display:flex;flex-wrap:wrap;gap:5px;"></div>
            </div>
        `;

        wrapper.html(html);

        const input = wrapper.find(`#assigned_to_input_${cdn}`);
        const badge_container = wrapper.find(`#assigned_to_badges_${cdn}`);

        function renderBadges(users) {
            badge_container.empty();
            users.forEach(user => {
                const badge = $(`<span class="badge badge-primary">${user}</span>`);
                badge_container.append(badge);
            });
        }

        renderBadges(current_users);
        input.val(current_users.join(", "));

        input.on("change blur", function () {
            const users = input.val()
                .split(",")
                .map(u => u.trim())
                .filter(Boolean);
            frappe.model.set_value(cdt, cdn, "assigned_users", users.join(","));
            renderBadges(users);
        });
    });
}
