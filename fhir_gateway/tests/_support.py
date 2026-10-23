"""Shared test helpers used across fhir_gateway's test modules. Not itself a test module -- Frappe's
test runner only discovers test_*.py files, so this is never collected or run directly."""

import frappe


def ensure_gender(value):
	"""Idempotently ensure a Gender record exists. No app ships a single Gender record as a fixture
	(confirmed: not frappe, erpnext, or healthcare) -- a long-lived dev site accumulates them
	organically (e.g. the first Patient or Practitioner ever created through Desk), but a fresh CI
	site has none at all. Any test that sets a sex/gender Link value must seed it first, or insert
	fails with LinkValidationError."""
	if value and not frappe.db.exists("Gender", value):
		frappe.get_doc({"doctype": "Gender", "gender": value}).insert(ignore_permissions=True)


def make_patient(**fields):
	# invite_user=0: healthcare's own Patient controller auto-creates a linked User when `email` is
	# set unless this is explicitly off -- a side effect most callers have no interest in and that
	# would otherwise leak a User record their tearDown doesn't know to clean up.
	values = {"doctype": "Patient", "sex": "Male", "first_name": "Test", "invite_user": 0}
	values.update(fields)
	ensure_gender(values.get("sex"))
	doc = frappe.get_doc(values)
	doc.insert(ignore_permissions=True)
	return doc


def make_practitioner(**fields):
	values = {"doctype": "Healthcare Practitioner", "first_name": "Test", "status": "Active"}
	values.update(fields)
	ensure_gender(values.get("gender"))
	doc = frappe.get_doc(values)
	doc.insert(ignore_permissions=True)
	return doc
