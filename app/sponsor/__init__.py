from flask import Blueprint

sponsor_bp = Blueprint("sponsor", __name__)

from app.sponsor import routes