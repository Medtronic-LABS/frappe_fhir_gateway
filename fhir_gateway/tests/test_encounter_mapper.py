"""Integration test for mappers/encounter.py -- never got one in the first phase; filling that gap
here alongside the deeper resource-coverage work."""

import unittest

import frappe

from fhir_gateway.mappers import encounter as encounter_mapper
from fhir_gateway.tests._support import ensure_appointment_type, ensure_practitioner, make_patient


class TestEncounterMapper(unittest.TestCase):
	def setUp(self):
		self._docs = []

	def tearDown(self):
		for doctype, name in reversed(self._docs):
			if frappe.db.exists(doctype, name):
				frappe.delete_doc(doctype, name, ignore_permissions=True, delete_permanently=True, force=True)
		frappe.db.commit()

	def _make_encounter(self, **fields):
		patient = make_patient(first_name="Enc Test")
		self._docs.append(("Patient", patient.name))

		values = {
			"doctype": "Patient Encounter",
			"patient": patient.name,
			"practitioner": ensure_practitioner(),
			"encounter_date": "2026-01-01",
			"encounter_time": "10:00:00",
			"appointment_type": ensure_appointment_type(),
		}
		values.update(fields)
		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True)
		self._docs.append(("Patient Encounter", doc.name))
		return doc

	def test_to_fhir_basic_shape(self):
		doc = self._make_encounter(status="Completed")
		resource = encounter_mapper.to_fhir(doc)

		self.assertEqual(resource["resourceType"], "Encounter")
		self.assertEqual(resource["id"], doc.name)
		self.assertEqual(resource["status"], "finished")
		self.assertEqual(resource["subject"], {"reference": f"Patient/{doc.patient}"})
		self.assertEqual(resource["period"]["start"], "2026-01-01T10:00:00")

	def test_every_real_status_option_is_mapped(self):
		meta = frappe.get_meta("Patient Encounter")
		status_field = meta.get_field("status")
		real_statuses = [s for s in (status_field.options or "").split("\n") if s]
		for status in real_statuses:
			self.assertIn(status, encounter_mapper._STATUS_MAP, f"{status!r} has no explicit mapping")
