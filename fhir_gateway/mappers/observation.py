"""`healthcare` `Observation` -> FHIR `Observation`. Read-only (egress).

FHIR's `Observation` resource type is federated here across TWO source doctypes: `Observation`
itself (lab/general results) and `Vital Signs` (see vital_signs.py) -- both are genuinely
Observations in FHIR's model, just stored in two different Frappe doctypes. `get`/`search` check
both sources rather than assuming one doctype per resource type, unlike every other mapper in this
app.
"""

import frappe

from fhir_gateway.mappers import vital_signs
from fhir_gateway.mappers._shared import (
	as_float,
	as_str_datetime,
	codification_to_coding,
	strip_fhir_date_prefix,
	strip_reference_prefix,
)

DOCTYPE = "Observation"  # the primary source; vital_signs.DOCTYPE is the secondary one
RESOURCE_TYPE = "Observation"

# router.py checks permission against every doctype here, not just DOCTYPE -- a caller reading
# this resource type must be permitted on BOTH source doctypes, since either one can produce data
# under it.
ALL_DOCTYPES = [DOCTYPE, vital_signs.DOCTYPE]

SEARCH_PARAMS = {
	"patient": "reference",
	"_lastUpdated": "date",
}

# Observation.status here is already a plain Select whose values match FHIR's own
# Observation.status ValueSet almost verbatim (http://hl7.org/fhir/ValueSet/observation-status,
# also seeded as Code Value data in healthcare/setup.py) -- just needs lowercasing and the one
# "Entered in Error" -> "entered-in-error" spelling difference.
_STATUS_MAP = {
	"Registered": "registered",
	"Preliminary": "preliminary",
	"Final": "final",
	"Amended": "amended",
	"Corrected": "corrected",
	"Cancelled": "cancelled",
	"Entered in Error": "entered-in-error",
	"Unknown": "unknown",
	"Approved": "final",
	"Rejected": "cancelled",
}

_CATEGORY_MAP = {
	"Social History": "social-history",
	"Vital Signs": "vital-signs",
	"Imaging": "imaging",
	"Laboratory": "laboratory",
	"Procedure": "procedure",
	"Survey": "survey",
	"Exam": "exam",
	"Therapy": "therapy",
	"Activity": "activity",
}


def to_fhir(doc):
	if doc.doctype == vital_signs.DOCTYPE:
		return vital_signs.to_fhir(doc)
	return _from_observation_doc(doc)


def _from_observation_doc(doc):
	resource = {
		"resourceType": RESOURCE_TYPE,
		"id": doc.name,
		"status": _STATUS_MAP.get(doc.status, "unknown"),
		"subject": {"reference": f"Patient/{doc.patient}"},
	}
	coding = codification_to_coding(doc.codification_table)
	resource["code"] = {"coding": coding} if coding else {"text": doc.observation_template or doc.name}
	if doc.observation_category:
		resource["category"] = [
			{
				"coding": [
					{
						"system": "http://terminology.hl7.org/CodeSystem/observation-category",
						"code": _CATEGORY_MAP.get(doc.observation_category, "exam"),
					}
				]
			}
		]
	effective = as_str_datetime(doc.result_datetime) or as_str_datetime(doc.posting_date)
	if effective:
		resource["effectiveDateTime"] = effective
	_set_value(resource, doc)
	if doc.healthcare_practitioner:
		resource["performer"] = [{"reference": f"Practitioner/{doc.healthcare_practitioner}"}]
	if doc.modified:
		resource["meta"] = {"lastUpdated": as_str_datetime(doc.modified)}
	return resource


def _set_value(resource, doc):
	data_type = doc.permitted_data_type
	if data_type == "Quantity" or data_type == "Numeric":
		value = as_float(doc.result_float)
		if value is not None:
			resource["valueQuantity"] = {"value": value, "unit": doc.permitted_unit or ""}
			return
	if data_type == "Boolean":
		if doc.result_boolean:
			resource["valueBoolean"] = doc.result_boolean == "Yes" or doc.result_boolean is True
			return
	if doc.result_text:
		resource["valueString"] = doc.result_text
	elif doc.result_data:
		resource["valueString"] = doc.result_data


def build_filters(args):
	filters = {}
	if args.get("patient"):
		filters["patient"] = strip_reference_prefix(args["patient"], "Patient")
	if args.get("_lastUpdated"):
		filters["modified"] = (">=", strip_fhir_date_prefix(args["_lastUpdated"]))
	return filters


def get(name):
	"""Checks `Observation` first, then `Vital Signs` -- a FHIR `id` can belong to either source."""
	if frappe.db.exists(DOCTYPE, name):
		return frappe.get_doc(DOCTYPE, name)
	if frappe.db.exists(vital_signs.DOCTYPE, name):
		return frappe.get_doc(vital_signs.DOCTYPE, name)
	return None


def search(filters, limit, offset):
	"""Merges matches from both source doctypes, sorted by `modified desc`, then paginates across
	the combined set. Fetches every matching name (with `modified`) from both tables rather than
	pushing LIMIT/OFFSET to SQL -- the simplest correct way to paginate a UNION of two tables; fine
	at this app's expected data volumes, called out here as a known trade-off rather than silently
	accepted."""
	rows = frappe.get_all(DOCTYPE, filters=filters, fields=["name", "modified"]) + [
		dict(r, _source=vital_signs.DOCTYPE)
		for r in frappe.get_all(vital_signs.DOCTYPE, filters=filters, fields=["name", "modified"])
	]
	for r in rows:
		r.setdefault("_source", DOCTYPE)
	rows.sort(key=lambda r: r["modified"], reverse=True)

	total = len(rows)
	page = rows[offset : offset + limit]
	resources = [to_fhir(frappe.get_doc(r["_source"], r["name"])) for r in page]
	return resources, total
