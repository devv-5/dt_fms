import frappe



def validate(doc, method):
    set_delay_duration(doc)


def set_delay_duration(doc):
    if doc.custom_tat and doc.custom_time_taken_to_close:
        doc.delay_duration = doc.custom_time_taken_to_close - doc.custom_tat
