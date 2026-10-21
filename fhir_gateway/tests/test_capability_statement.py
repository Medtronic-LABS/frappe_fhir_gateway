"""The CapabilityStatement must declare exactly the resources router.py actually implements --
this is the contract an external system (OpenHIM included) discovers the API shape from, so a
mismatch here is worse than no CapabilityStatement at all."""

import unittest

from fhir_gateway import capability
from fhir_gateway.router import SUPPORTED_RESOURCES


class TestCapabilityStatement(unittest.TestCase):
	def test_declares_exactly_the_supported_resource_types(self):
		statement = capability.build()
		declared = {r["type"] for r in statement["rest"][0]["resource"]}
		self.assertEqual(declared, set(SUPPORTED_RESOURCES.keys()))

	def test_every_declared_resource_supports_read_and_search(self):
		statement = capability.build()
		for resource in statement["rest"][0]["resource"]:
			codes = {i["code"] for i in resource["interaction"]}
			self.assertIn("read", codes)
			self.assertIn("search-type", codes)

	def test_shape(self):
		statement = capability.build()
		self.assertEqual(statement["resourceType"], "CapabilityStatement")
		self.assertEqual(statement["fhirVersion"], "4.0.1")
		self.assertEqual(statement["status"], "active")

	def test_response_is_fhir_json(self):
		resp = capability.response()
		self.assertEqual(resp.status_code, 200)
		self.assertEqual(resp.mimetype, "application/fhir+json")
