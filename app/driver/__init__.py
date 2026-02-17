from flask import Blueprint

driver_bp = Blueprint("driver", __name__)

from app.driver import routes
