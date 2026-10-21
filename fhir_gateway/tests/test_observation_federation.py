"""mappers/observation.py federates two source doctypes (Observation, Vital Signs) under one FHIR
resourceType -- this is the one mapper in this app where get()/search() aren't a thin wrapper
around a single doctype, so it gets its own dedicated test beyond the per-field mapping checks."""

import unittest

import frappe

from fhir_gateway.mappers import observation as obs_mapper
from fhir_gateway.mappers import vital_signs as vs_mapper
from fhir_gateway.router import SUPPORTED_RESOURCES


class TestObservationFederation(unittest.TestCase):
	def setUp(self):
		self._docs = []
		self.patient = frappe.get_doc(
			{"doctype": "Patient", "sex": "Male", "first_name": "Obs Fed Test", "invite_user": 0}
		)
		self.patient.insert(ignore_permissions=True)
		self._docs.append(("Patient", self.patient.name))

	def tearDown(self):
		for doctype, name in reversed(self._docs):
			if frappe.db.exists(doctype, name):
				frappe.delete_doc(doctype, name, ignore_permissions=True, delete_permanently=True, force=True)
		frappe.db.commit()

	def _make_vital_signs(self, **fields):
		values = {
			"doctype": "Vital Signs",
			"patient": self.patient.name,
			"signs_date": "2026-01-01",
			"signs_time": "09:00:00",
		}
		values.update(fields)
		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True)
		self._docs.append(("Vital Signs", doc.name))
		return doc

	def _make_observation(self, **fields):
		company = frappe.get_all("Company", limit=1)
		obs_template = frappe.get_all("Observation Template", limit=1)
		values = {
			"doctype": "Observation",
			"patient": self.patient.name,
			"company": company[0].name if company else None,
			"observation_category": "Laboratory",
			"observation_template": obs_template[0].name if obs_template else None,
		}
		values.update(fields)
		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True)
		self._docs.append(("Observation", doc.name))
		return doc

	def test_registered_under_observation_resource_type(self):
		self.assertIn("Observation", SUPPORTED_RESOURCES)
		self.assertIs(SUPPORTED_RESOURCES["Observation"], obs_mapper)

	def test_requires_permission_on_both_source_doctypes(self):
		self.assertEqual(obs_mapper.ALL_DOCTYPES, ["Observation", "Vital Signs"])

	def test_vital_signs_row_becomes_one_observation_with_components(self):
		doc = self._make_vital_signs(temperature=37.2, pulse=78, bp_systolic=120, bp_diastolic=80)

		resource = obs_mapper.to_fhir(doc)

		self.assertEqual(resource["resourceType"], "Observation")
		self.assertEqual(resource["id"], doc.name)
		self.assertEqual(resource["category"][0]["coding"][0]["code"], "vital-signs")
		codes = {c["code"]["coding"][0]["code"] for c in resource["component"]}
		self.assertEqual(codes, {"8310-5", "8867-4", "8480-6", "8462-4"})

	def test_vital_signs_with_no_readings_has_no_components(self):
		doc = self._make_vital_signs()
		resource = vs_mapper.to_fhir(doc)
		self.assertNotIn("component", resource)

	def test_get_finds_a_vital_signs_row_by_id(self):
		vs = self._make_vital_signs(temperature=36.9)
		found = obs_mapper.get(vs.name)
		self.assertIsNotNone(found)
		self.assertEqual(found.doctype, "Vital Signs")

	def test_get_finds_an_observation_row_by_id(self):
		obs = self._make_observation()
		found = obs_mapper.get(obs.name)
		self.assertIsNotNone(found)
		self.assertEqual(found.doctype, "Observation")

	def test_get_returns_none_for_unknown_id(self):
		self.assertIsNone(obs_mapper.get("not-a-real-id-in-either-doctype"))

	def test_search_merges_both_sources_for_the_same_patient(self):
		self._make_vital_signs(temperature=37.0)
		self._make_observation()

		resources, total = obs_mapper.search({"patient": self.patient.name}, limit=50, offset=0)

		self.assertEqual(total, 2)
		self.assertEqual(len(resources), 2)
		self.assertTrue(all(r["resourceType"] == "Observation" for r in resources))

	def test_search_pagination_spans_the_combined_set(self):
		self._make_vital_signs(temperature=37.0)
		self._make_observation()

		page1, total = obs_mapper.search({"patient": self.patient.name}, limit=1, offset=0)
		page2, _ = obs_mapper.search({"patient": self.patient.name}, limit=1, offset=1)

		self.assertEqual(total, 2)
		self.assertEqual(len(page1), 1)
		self.assertEqual(len(page2), 1)
		self.assertNotEqual(page1[0]["id"], page2[0]["id"])
