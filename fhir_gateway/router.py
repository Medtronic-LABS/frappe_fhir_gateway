"""Parses `/fhir/<Type>[/<id>][?params]` and dispatches to the right mapper.

Kept deliberately small: resource-type lookup, auth/permission gating, then hand off to the
mapper's own `get`/`search`/`build_filters`. All the FHIR-shape knowledge lives in the mappers and
in `search.py`/`outcome.py`, not here.
"""

import orjson
from werkzeug.wrappers import Response

import frappe
from fhir_gateway import outcome, search
from fhir_gateway.mappers import (
	diagnostic_report,
	encounter,
	medication_request,
	observation,
	patient,
	practitioner,
)

FHIR_JSON = "application/fhir+json"

# resourceType -> mapper module. The one place that decides what this gateway exposes --
# capability.py and docs/openapi.yaml must both match this exactly. Observation's mapper also
# covers Vital Signs internally (see mappers/observation.py's module docstring) -- that's not a
# separate entry here, since it's not a separate FHIR resourceType.
SUPPORTED_RESOURCES = {
	patient.RESOURCE_TYPE: patient,
	encounter.RESOURCE_TYPE: encounter,
	observation.RESOURCE_TYPE: observation,
	practitioner.RESOURCE_TYPE: practitioner,
	medication_request.RESOURCE_TYPE: medication_request,
	diagnostic_report.RESOURCE_TYPE: diagnostic_report,
}


def route(path):
	"""`path` is the stripped request path, e.g. `fhir/Patient/abc123` or `fhir/Patient` or
	`fhir/metadata`. Returns a werkzeug Response in every case -- never raises, so a caller never
	gets Frappe's own default error page for anything under /fhir/."""
	segments = [s for s in path.split("/") if s]
	rest = segments[1:]  # drop the leading "fhir"

	if not rest:
		return outcome.not_found("No resource type specified. Try /fhir/metadata.")

	if rest[0] == "metadata":
		from fhir_gateway import capability

		return capability.response()

	resource_type = rest[0]
	resource_id = rest[1] if len(rest) > 1 else None

	mapper = SUPPORTED_RESOURCES.get(resource_type)
	if not mapper:
		return outcome.not_supported(f"Unsupported resource type: {resource_type}")

	if frappe.session.user == "Guest":
		return outcome.unauthorized()

	# A resource type's data can come from more than one source doctype (Observation also reads
	# Vital Signs -- see mappers/observation.py); a caller must be permitted on every one of them,
	# not just the mapper's primary DOCTYPE.
	required_doctypes = getattr(mapper, "ALL_DOCTYPES", [mapper.DOCTYPE])
	if not all(frappe.has_permission(dt, "read") for dt in required_doctypes):
		return outcome.forbidden(f"Not permitted to read {resource_type}.")

	try:
		if resource_id:
			return _handle_read(mapper, resource_type, resource_id)
		return _handle_search(mapper, resource_type)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"fhir_gateway: {resource_type} request failed")
		return outcome.server_error()


def _handle_read(mapper, resource_type, resource_id):
	doc = mapper.get(resource_id)
	if not doc:
		return outcome.not_found(f"{resource_type}/{resource_id} not found.")
	resource = mapper.to_fhir(doc)
	return Response(orjson.dumps(resource), status=200, mimetype=FHIR_JSON)


def _handle_search(mapper, resource_type):
	args = frappe.local.request.args
	filters = mapper.build_filters(args)
	count = search.parse_count(args)
	offset = search.parse_offset(args)
	resources, total = mapper.search(filters, count, offset)
	base_url = frappe.utils.get_url()
	return search.response(resource_type, resources, total, base_url, args, count, offset)
