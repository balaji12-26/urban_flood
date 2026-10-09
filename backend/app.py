"""
FloodSense Flask app. Serves the API and the static vanilla frontend.
"""
import os

from flask import Flask, send_from_directory, jsonify

from backend.config import CACHE_DIR

_FRONTEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))


def create_app() -> Flask:
    app = Flask(__name__, static_folder=_FRONTEND, static_url_path="")
    app.json.sort_keys = False
    os.makedirs(CACHE_DIR, exist_ok=True)

    from backend.routes.zones import bp as zones_bp
    from backend.routes.scenario import bp as scenario_bp
    from backend.routes.forecast_curve import bp as forecast_bp
    from backend.routes.validation_routes import bp as validation_bp
    app.register_blueprint(zones_bp)
    app.register_blueprint(scenario_bp)
    app.register_blueprint(forecast_bp)
    app.register_blueprint(validation_bp)

    @app.get("/")
    def index():
        return send_from_directory(_FRONTEND, "index.html")

    @app.get("/mock/mock.json")
    def mock_json():
        return send_from_directory(os.path.join(_FRONTEND, "..", "mock"), "mock.json")

    @app.after_request
    def no_cache_api(resp):
        if resp.mimetype == "application/json":
            resp.headers["Cache-Control"] = "no-store"
            resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    @app.errorhandler(404)
    def not_found(_):
        return jsonify({"error": "not found"}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "internal error", "detail": str(e)[:200]}), 500

    return app


app = create_app()
