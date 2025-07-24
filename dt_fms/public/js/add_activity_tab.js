// frappe.ui.form.on('Purchase Order', {
//     refresh: function(frm) {
//         console.log("Form refreshed for doctype:", frm.doctype);
//         // Only for non-single doctypes (ignore e.g. System Settings)
//         if(frm.is_new() || frm.is_single) return;

//         // Add Activities section only once
//         if (!frm.fields_dict.activities_html) {
//             frm.add_custom_field({
//                 fieldtype: 'Section Break',
//                 label: 'Activities',
//                 fieldname: 'activities_section'
//             });

//             frm.add_custom_field({
//                 fieldtype: 'HTML',
//                 fieldname: 'activities_html'
//             });

//             // Load related ToDos when form loads
//             load_todos(frm);
//         }
//     }
// });

// function load_todos(frm) {
//     frappe.call({
//         method: 'frappe.client.get_list',
//         args: {
//             doctype: 'ToDo',
//             filters: {
//                 reference_type: frm.doctype,
//                 reference_name: frm.docname
//             },
//             fields: ['name', 'description']
//         },
//         callback: function(r) {
//             let todos = r.message || [];
//             let html = '<div><b>ToDo for this Document:</b><br>';
//             if (todos.length) {
//                 todos.forEach(todo => {
//                     html += `<div style="padding:5px 0;">
//                         <a href="/app/todo/${todo.name}" target="_blank">${todo.description || 'No Description'}</a>
//                     </div>`;
//                 });
//             } else {
//                 html += '<p>No ToDos yet.</p>';
//             }

//             html += `<button class="btn btn-sm btn-primary" onclick="create_todo('${frm.doctype}','${frm.docname}')">New ToDo</button>`;
//             html += '</div>';

//             frm.fields_dict.activities_html.$wrapper.html(html);
//         }
//     });
// }
