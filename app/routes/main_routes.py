from __future__ import annotations

from flask import Blueprint

from ..controllers.main_controller import MainController


class MainRoutes:
    def __init__(self):
        self.bp = Blueprint("main", __name__)
        self.controller = MainController()

    def register(self):
        self.bp.route("/")(self.controller.home)
        self.bp.route("/dashboard")(self.controller.dashboard)
        self.bp.route("/media/<path:filename>")(self.controller.media)
        return self.bp

