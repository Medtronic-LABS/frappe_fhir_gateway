"""`healthcare` `Diagnostic Report` -> FHIR `DiagnosticReport`. Read-only (egress)."""

from functools import partial

from fhir_gateway.mappers._shared import as_str_datetime, get_doc, search_docs, strip_fhir_date_prefix, strip_reference_prefix

DOCTYPE = "Diagnostic Report"
RESOURCE_TYPE = "DiagnosticReport"

SEARCH_PARAMS = {
	"patient": "reference",
	"_lastUpdated": "date",
}

# Diagnostic Report.status (plain Select) isn't drawn from a Code Value/FHIR ValueSet --
# translated into FHIR's DiagnosticReport.status vocabulary by hand.
_STATUS_MAP = {
	"Open": "registered",
	"Pending Review": "preliminary",
	"Partially Approved": "partial",
	"Approved": "final",
	"Rejected": "cancelled",
}


def to_fhir(doc):
	resource = {
		"resourceType": RESOURCE_TYPE,
		"id": doc.name,
		"status": _STATUS_MAP.get(doc.status, "unknown"),
		# Not doc.title: healthcare's own controller auto-computes it as a patient-demographic
		# summary ("Ramesh Kumar - Male"), not a description of what the report is -- confirmed
		# empirically, not assumed. doc.name is a neutral, always-present fallback; ref_doctype
		# (what generated this report, e.g. a Lab Test) would be a better source if this gateway
		# starts mapping that resource type too.
		"code": {"text": doc.name},
		"subject": {"reference": f"Patient/{doc.patient}"},
	}
	if doc.practitioner:
		resource["performer"] = [{"reference": f"Practitioner/{doc.practitioner}"}]
	if doc.reference_posting_date:
		resource["effectiveDateTime"] = as_str_datetime(doc.reference_posting_date)
	if doc.sample_collection:
		resource["specimen"] = [{"reference": f"Specimen/{doc.sample_collection}"}]
	if doc.modified:
		resource["meta"] = {"lastUpdated": as_str_datetime(doc.modified)}
	return resource


def build_filters(args):
	filters = {}
	if args.get("patient"):
		filters["patient"] = strip_reference_prefix(args["patient"], "Patient")
	if args.get("_lastUpdated"):
		filters["modified"] = (">=", strip_fhir_date_prefix(args["_lastUpdated"]))
	return filters


get = partial(get_doc, DOCTYPE)
search = partial(search_docs, DOCTYPE, to_fhir)
