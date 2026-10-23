"""Integration test for mappers/diagnostic_report.py -- a real Diagnostic Report row (this doctype
has no mandatory fields, so a real insert is cheap here)."""

import unittest

import frappe

from fhir_gateway.mappers import diagnostic_report as dr_mapper
from fhir_gateway.tests._support import make_patient


class TestDiagnosticReportMapper(unittest.TestCase):
	def setUp(self):
		self._docs = []

	def tearDown(self):
		for doctype, name in reversed(self._docs):
			if frappe.db.exists(doctype, name):
				frappe.delete_doc(doctype, name, ignore_permissions=True, delete_permanently=True, force=True)
		frappe.db.commit()

	def _make_report(self, **fields):
		patient = make_patient(first_name="DR Test")
		self._docs.append(("Patient", patient.name))

		values = {"doctype": "Diagnostic Report", "patient": patient.name, "title": "Test Report"}
		values.update(fields)
		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True)
		self._docs.append(("Diagnostic Report", doc.name))
		return doc

	def test_to_fhir_basic_shape(self):
		# title is NOT a reliable "what is this report" source -- healthcare's own controller
		# overwrites it with an auto-computed patient-demographic summary on save (confirmed
		# empirically; see the mapper's comment), so this test doesn't assert on it.
		doc = self._make_report(status="Approved")
		resource = dr_mapper.to_fhir(doc)

		self.assertEqual(resource["resourceType"], "DiagnosticReport")
		self.assertEqual(resource["id"], doc.name)
		self.assertEqual(resource["status"], "final")
		self.assertEqual(resource["code"]["text"], doc.name)
		self.assertEqual(resource["subject"], {"reference": f"Patient/{doc.patient}"})

	def test_every_real_status_option_is_mapped(self):
		meta = frappe.get_meta("Diagnostic Report")
		status_field = meta.get_field("status")
		real_statuses = [s for s in (status_field.options or "").split("\n") if s]
		for status in real_statuses:
			self.assertIn(status, dr_mapper._STATUS_MAP, f"{status!r} has no explicit mapping")
