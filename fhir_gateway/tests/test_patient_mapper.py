"""Integration test for mappers/patient.py -- a real Patient row, since the mapping (name
composition, gender translation, telecom) is only meaningfully verified against real field values,
not isolatable pure logic."""

import unittest

import frappe

from fhir_gateway.mappers import patient as patient_mapper


class TestPatientMapper(unittest.TestCase):
	def setUp(self):
		self._docs = []

	def tearDown(self):
		for doctype, name in reversed(self._docs):
			if frappe.db.exists(doctype, name):
				frappe.delete_doc(doctype, name, ignore_permissions=True, delete_permanently=True, force=True)
		frappe.db.commit()

	def _make_patient(self, **fields):
		# invite_user=0: healthcare's own Patient controller auto-creates a linked User when
		# `email` is set unless this is explicitly off -- a side effect this test has no interest
		# in and that would otherwise leak a User record this tearDown doesn't clean up.
		values = {"doctype": "Patient", "sex": "Male", "first_name": "Test", "invite_user": 0}
		values.update(fields)
		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True)
		self._docs.append(("Patient", doc.name))
		return doc

	def test_to_fhir_basic_shape(self):
		doc = self._make_patient(
			first_name="Ramesh",
			last_name="Kumar",
			sex="Male",
			dob="1970-01-01",
			phone="9876500001",
			email="ramesh@example.com",
			status="Active",
		)

		resource = patient_mapper.to_fhir(doc)

		self.assertEqual(resource["resourceType"], "Patient")
		self.assertEqual(resource["id"], doc.name)
		self.assertTrue(resource["active"])
		self.assertEqual(resource["gender"], "male")
		self.assertEqual(resource["birthDate"], "1970-01-01")
		self.assertIn({"system": "phone", "value": "9876500001"}, resource["telecom"])
		self.assertIn({"system": "email", "value": "ramesh@example.com"}, resource["telecom"])
		self.assertEqual(resource["name"][0]["family"], "Kumar")
		self.assertIn("Ramesh", resource["name"][0]["given"])

	def test_inactive_status_maps_to_active_false(self):
		doc = self._make_patient(first_name="Inactive", sex="Female", status="Disabled")
		resource = patient_mapper.to_fhir(doc)
		self.assertFalse(resource["active"])

	def test_every_real_gender_option_is_mapped(self):
		"""Every option healthcare's own Gender doctype actually ships must have an explicit
		entry in _GENDER_MAP -- this caught a real bug ("Other" silently falling through to
		"unknown") during implementation."""
		real_genders = frappe.get_all("Gender", pluck="name")
		for gender in real_genders:
			self.assertIn(gender, patient_mapper._GENDER_MAP, f"{gender!r} has no explicit mapping")

	def test_truly_unmapped_gender_falls_back_to_unknown(self):
		# A pure unit test on the translation function, not a full Patient round-trip: healthcare's
		# Gender doctype is a Link field, so a real inserted Patient can never carry a value
		# outside that doctype's own real options (Frappe validates Link targets at insert) --
		# there is no real *document* state that exercises this fallback, only a hypothetical
		# future Gender option this app hasn't been updated for yet.
		self.assertEqual(patient_mapper._gender_fhir("Some New Gender Option"), "unknown")

	def test_get_returns_none_for_missing_id(self):
		self.assertIsNone(patient_mapper.get("Patient-Does-Not-Exist"))

	def test_build_filters_strips_fhir_date_prefix(self):
		filters = patient_mapper.build_filters({"_lastUpdated": "gt2026-01-01"})
		self.assertEqual(filters["modified"], (">=", "2026-01-01"))
