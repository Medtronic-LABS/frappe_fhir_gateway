"""The one entrypoint Frappe's website router calls for every request under `/fhir/*`.

Registered via `hooks.py`'s `page_renderer` list. `PathResolver` (frappe/website/path_resolver.py)
tries every registered custom renderer, in order, before its own HTML renderers -- `can_render()`
decides whether this one claims the path, `render()` must return a real `werkzeug.wrappers.Response`
(the type `get_response()` in frappe/website/serve.py returns directly, untouched).
"""

from frappe.website.page_renderers.base_renderer import BaseRenderer

from fhir_gateway.router import route


class FHIRPageRenderer(BaseRenderer):
	def can_render(self):
		return self.path == "fhir" or self.path.startswith("fhir/")

	def render(self):
		return route(self.path)
