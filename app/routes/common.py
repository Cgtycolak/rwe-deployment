"""Helpers shared by the route modules."""
from flask import current_app, jsonify


def api_error(route_name, e):
    """Log the exception and return a generic 500. Never send str(e) to the client."""
    current_app.logger.error(f"Error in {route_name}: {e}", exc_info=True)
    return jsonify({'code': 500, 'error': 'Internal server error'}), 500
