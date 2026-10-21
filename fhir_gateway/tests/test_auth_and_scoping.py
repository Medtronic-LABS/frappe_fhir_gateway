"""Auth/permission gating in router.route() -- the whole point of this gateway's security model is
that API-key auth resolves to a real frappe.set_user(), and the "FHIR Integration" role's
Custom DocPerm fixture is what actually scopes a caller, not any bespoke token-validation code.
These tests exercise that directly rather than mocking it away."""

import json
import unittest

import frappe

from fhir_gateway import router


class TestAuthAndScoping(unittest.TestCase):
	def setUp(self):
		self._docs = []
		self._users = []
		self._addCleanup_user = frappe.session.user

	def tearDown(self):
		frappe.set_user("Administrator")
		for doctype, name in reversed(self._docs):
			if frappe.db.exists(doctype, name):
				frappe.delete_doc(doctype, name, ignore_permissions=True, delete_permanently=True, force=True)
		for user in self._users:
			if frappe.db.exists("User", user):
				frappe.delete_doc("User", user, ignore_permissions=True, force=True)
		frappe.db.commit()
		frappe.set_user(self._addCleanup_user)

	def _make_scoped_user(self, email, role="FHIR Integration"):
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "FHIR Test",
				"send_welcome_email": 0,
				"user_type": "System User",
				"roles": [{"role": role}],
			}
		)
		user.insert(ignore_permissions=True)
		self._users.append(email)
		return user

	def _make_patient(self):
		doc = frappe.get_doc({"doctype": "Patient", "sex": "Male", "first_name": "Auth Test"})
		doc.insert(ignore_permissions=True)
		self._docs.append(("Patient", doc.name))
		return doc

	def test_guest_is_unauthorized(self):
		frappe.set_user("Guest")
		resp = router.route("fhir/Patient/whatever")
		self.assertEqual(resp.status_code, 401)
		body = json.loads(resp.get_data())
		self.assertEqual(body["resourceType"], "OperationOutcome")
		self.assertEqual(body["issue"][0]["code"], "login")

	def test_user_without_role_is_forbidden(self):
		user = self._make_scoped_user("no-role.fhir-test@example.com", role="Guest")
		frappe.set_user(user.name)
		resp = router.route("fhir/Patient/whatever")
		self.assertEqual(resp.status_code, 403)
		body = json.loads(resp.get_data())
		self.assertEqual(body["issue"][0]["code"], "forbidden")

	def test_unsupported_resource_type_is_404_not_supported(self):
		frappe.set_user("Administrator")
		resp = router.route("fhir/SomeDoctypeNotExposed")
		self.assertEqual(resp.status_code, 404)
		body = json.loads(resp.get_data())
		self.assertEqual(body["issue"][0]["code"], "not-supported")

	def test_no_resource_type_is_404(self):
		resp = router.route("fhir")
		self.assertEqual(resp.status_code, 404)

	def test_missing_record_is_404_not_found(self):
		frappe.set_user("Administrator")
		resp = router.route("fhir/Patient/does-not-exist")
		self.assertEqual(resp.status_code, 404)
		body = json.loads(resp.get_data())
		self.assertEqual(body["issue"][0]["code"], "not-found")

	def test_scoped_user_can_read_a_permitted_resource(self):
		patient = self._make_patient()
		user = self._make_scoped_user("scoped.fhir-test@example.com")
		frappe.set_user(user.name)

		resp = router.route(f"fhir/Patient/{patient.name}")

		self.assertEqual(resp.status_code, 200)
		self.assertEqual(resp.mimetype, "application/fhir+json")
		body = json.loads(resp.get_data())
		self.assertEqual(body["resourceType"], "Patient")
		self.assertEqual(body["id"], patient.name)
