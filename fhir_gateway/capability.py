"""`GET /fhir/metadata` -- the CapabilityStatement external systems (OpenHIM included) query first
to discover what this server actually supports. Guest-accessible, matching standard FHIR server
convention -- it describes the API's shape, not any patient data.

Declares exactly the resources/interactions `router.py` implements, kept in sync by hand (see
docs/openapi.yaml, which must also match).
"""

import orjson
from werkzeug.wrappers import Response

from fhir_gateway.outcome import FHIR_JSON
from fhir_gateway.router import SUPPORTED_RESOURCES


def build():
	return {
		"resourceType": "CapabilityStatement",
		"status": "active",
		"date": "2026-01-01",
		"kind": "instance",
		"software": {"name": "fhir_gateway", "version": "0.0.1"},
		"fhirVersion": "4.0.1",
		"format": ["json"],
		"rest": [
			{
				"mode": "server",
				"security": {
					"extension": [
						{
							"url": "http://fhir-authorization-extension",
							"valueString": (
								"Authorization: token <api_key>:<api_secret> "
								"(Frappe API key/secret, see docs/openapi.yaml)"
							),
						}
					]
				},
				"resource": [
					{
						"type": resource_type,
						"interaction": [{"code": "read"}, {"code": "search-type"}],
						"searchParam": [
							{"name": name, "type": search_type}
							for name, search_type in mapper.SEARCH_PARAMS.items()
						],
					}
					for resource_type, mapper in SUPPORTED_RESOURCES.items()
				],
			}
		],
	}


def response():
	return Response(orjson.dumps(build()), status=200, mimetype=FHIR_JSON)
