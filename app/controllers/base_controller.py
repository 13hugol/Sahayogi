from __future__ import annotations

from flask import render_template


class BaseController:
    def render(self, template_name: str, **context):
        return render_template(template_name, **context)

