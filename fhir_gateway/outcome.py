"""FHIR `OperationOutcome` responses for every error path this gateway can hit.

A FHIR server signals errors with an OperationOutcome resource, not a generic error JSON shape --
callers (OpenHIM included) parse `issue[].code`/`severity`, not an ad-hoc `{"error": "..."}" body.
`code` values are from FHIR's own IssueType value set (http://hl7.org/fhir/valueset-issue-type.html);
only the ones this gateway actually produces are used here.
"""

import orjson
from werkzeug.wrappers import Response

FHIR_JSON = "application/fhir+json"


def _response(http_status, code, diagnostics, severity="error"):
	body = {
		"resourceType": "OperationOutcome",
		"issue": [{"severity": severity, "code": code, "diagnostics": diagnostics}],
	}
	return Response(orjson.dumps(body), status=http_status, mimetype=FHIR_JSON)


def unauthorized(diagnostics="Authentication required."):
	return _response(401, "login", diagnostics)


def forbidden(diagnostics="Not permitted to access this resource."):
	return _response(403, "forbidden", diagnostics)


def not_found(diagnostics="Resource not found."):
	return _response(404, "not-found", diagnostics)


def not_supported(diagnostics="Unsupported resource type."):
	return _response(404, "not-supported", diagnostics)


def bad_request(diagnostics="Malformed request."):
	return _response(400, "invalid", diagnostics)


def server_error(diagnostics="Internal error."):
	return _response(500, "exception", diagnostics)
