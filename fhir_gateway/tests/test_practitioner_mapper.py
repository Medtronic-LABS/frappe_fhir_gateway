"""Integration test for mappers/practitioner.py -- a real Healthcare Practitioner row."""

import unittest

import frappe

from fhir_gateway.mappers import practitioner as practitioner_mapper


class TestPractitionerMapper(unittest.TestCase):
	def setUp(self):
		self._docs = []

	def tearDown(self):
		for doctype, name in reversed(self._docs):
			if frappe.db.exists(doctype, name):
				frappe.delete_doc(doctype, name, ignore_permissions=True, delete_permanently=True, force=True)
		frappe.db.commit()

	def _make_practitioner(self, **fields):
		values = {"doctype": "Healthcare Practitioner", "first_name": "Test", "status": "Active"}
		values.update(fields)
		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True)
		self._docs.append(("Healthcare Practitioner", doc.name))
		return doc

	def test_to_fhir_basic_shape(self):
		doc = self._make_practitioner(
			first_name="Ananya",
			last_name="Rao",
			gender="Female",
			mobile_phone="9000000000",
			email_id="ananya@example.com",
			status="Active",
		)

		resource = practitioner_mapper.to_fhir(doc)

		self.assertEqual(resource["resourceType"], "Practitioner")
		self.assertEqual(resource["id"], doc.name)
		self.assertTrue(resource["active"])
		self.assertEqual(resource["gender"], "female")
		self.assertIn({"system": "phone", "value": "9000000000"}, resource["telecom"])
		self.assertEqual(resource["name"][0]["family"], "Rao")

	def test_disabled_status_maps_to_active_false(self):
		doc = self._make_practitioner(first_name="Disabled", status="Disabled")
		resource = practitioner_mapper.to_fhir(doc)
		self.assertFalse(resource["active"])
