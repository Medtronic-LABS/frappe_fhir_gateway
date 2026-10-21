"""Minimal FHIR search: param parsing + `Bundle(type=searchset)` wrapping + pagination.

Deliberately not full FHIR search grammar (no chaining, no `_include`/`_revinclude`, no modifiers
like `:exact`) -- see the plan's explicit scope boundary. `_count`/`Bundle.link[relation=next]`
pagination mirrors what `spice_next_core/fhir/pull.py` already consumes on the client side, so a
client written against that pattern works unmodified against this server too.
"""

import orjson
from werkzeug.wrappers import Response

from fhir_gateway.outcome import FHIR_JSON

DEFAULT_COUNT = 50
MAX_COUNT = 200


def parse_count(args):
	try:
		count = int(args.get("_count", DEFAULT_COUNT))
	except (TypeError, ValueError):
		count = DEFAULT_COUNT
	return max(1, min(count, MAX_COUNT))


def parse_offset(args):
	try:
		return max(0, int(args.get("_offset", 0)))
	except (TypeError, ValueError):
		return 0


def build_bundle(resource_type, resources, total, base_url, args, count, offset):
	entries = [{"resource": r} for r in resources]
	bundle = {
		"resourceType": "Bundle",
		"type": "searchset",
		"total": total,
		"entry": entries,
	}

	links = [{"relation": "self", "url": _page_url(base_url, resource_type, args, offset, count)}]
	if offset + count < total:
		links.append(
			{"relation": "next", "url": _page_url(base_url, resource_type, args, offset + count, count)}
		)
	bundle["link"] = links
	return bundle


def _page_url(base_url, resource_type, args, offset, count):
	params = {k: v for k, v in args.items() if k not in ("_count", "_offset")}
	params["_count"] = count
	params["_offset"] = offset
	query = "&".join(f"{k}={v}" for k, v in params.items())
	return f"{base_url}/fhir/{resource_type}?{query}"


def response(resource_type, resources, total, base_url, args, count, offset):
	bundle = build_bundle(resource_type, resources, total, base_url, args, count, offset)
	return Response(orjson.dumps(bundle), status=200, mimetype=FHIR_JSON)
