"""`healthcare` `Patient` -> FHIR `Patient`. Read-only (egress) for this MVP."""

from functools import partial

from fhir_gateway.mappers._shared import (
	as_str_datetime,
	get_doc,
	search_docs,
	strip_fhir_date_prefix,
)

DOCTYPE = "Patient"
RESOURCE_TYPE = "Patient"

# name -> FHIR search param type (declared in the CapabilityStatement; see capability.py)
SEARCH_PARAMS = {
	"identifier": "token",
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


def _gender_fhir(gender):
	return _GENDER_MAP.get(gender, "unknown")


def to_fhir(doc):
	name_text = doc.patient_name or " ".join(filter(None, [doc.first_name, doc.middle_name, doc.last_name]))
	resource = {
		"resourceType": RESOURCE_TYPE,
		"id": doc.name,
		"active": doc.status == "Active",
		"identifier": [{"system": "urn:fhir-gateway:patient", "value": doc.name}],
		"name": [
			{
				"text": name_text,
				"family": doc.last_name or None,
				"given": [p for p in (doc.first_name, doc.middle_name) if p],
			}
		],
		"gender": _gender_fhir(doc.sex),
	}
	if doc.dob:
		resource["birthDate"] = str(doc.dob)
	telecom = []
	if doc.phone or doc.mobile:
		telecom.append({"system": "phone", "value": doc.phone or doc.mobile})
	if doc.email:
		telecom.append({"system": "email", "value": doc.email})
	if telecom:
		resource["telecom"] = telecom
	if doc.modified:
		resource["meta"] = {"lastUpdated": as_str_datetime(doc.modified)}
	return resource


def build_filters(args):
	"""Translate the subset of query params this resource supports into Frappe `get_list` filters.
	Unknown params are ignored rather than erroring -- matches typical lenient FHIR server search
	behaviour for an unsupported param, rather than failing the whole request."""
	filters = {}
	if args.get("identifier"):
		filters["name"] = args["identifier"]
	if args.get("_lastUpdated"):
		filters["modified"] = (">=", strip_fhir_date_prefix(args["_lastUpdated"]))
	return filters


get = partial(get_doc, DOCTYPE)
search = partial(search_docs, DOCTYPE, to_fhir)
