"""`healthcare` `Healthcare Practitioner` -> FHIR `Practitioner`. Read-only (egress)."""

from functools import partial

from fhir_gateway.mappers._shared import as_str_datetime, get_doc, search_docs, strip_fhir_date_prefix

DOCTYPE = "Healthcare Practitioner"
RESOURCE_TYPE = "Practitioner"

SEARCH_PARAMS = {
	"_lastUpdated": "date",
}

_GENDER_MAP = {
	"Male": "male",
	"Female": "female",
	"Other": "other",
	"Transgender": "other",
	"Genderqueer": "other",
	"Non-Conforming": "other",
	"Prefer not to say": "unknown",
}


def to_fhir(doc):
	resource = {
		"resourceType": RESOURCE_TYPE,
		"id": doc.name,
		"active": doc.status == "Active",
		"name": [
			{
				"text": doc.practitioner_name or doc.first_name,
				"family": doc.last_name or None,
				"given": [p for p in (doc.first_name, doc.middle_name) if p],
			}
		],
	}
	if doc.gender:
		resource["gender"] = _GENDER_MAP.get(doc.gender, "unknown")
	telecom = []
	if doc.mobile_phone:
		telecom.append({"system": "phone", "value": doc.mobile_phone})
	if doc.email_id:
		telecom.append({"system": "email", "value": doc.email_id})
	if telecom:
		resource["telecom"] = telecom
	if doc.department:
		resource["qualification"] = [{"code": {"text": doc.department}}]
	if doc.modified:
		resource["meta"] = {"lastUpdated": as_str_datetime(doc.modified)}
	return resource


def build_filters(args):
	filters = {}
	if args.get("_lastUpdated"):
		filters["modified"] = (">=", strip_fhir_date_prefix(args["_lastUpdated"]))
	return filters


get = partial(get_doc, DOCTYPE)
search = partial(search_docs, DOCTYPE, to_fhir)
