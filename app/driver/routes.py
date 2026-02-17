from flask import render_template
from flask_login import login_required, current_user
from app.driver import driver_bp

@driver_bp.route("/dashboard")
@login_required
def dashboard():
    return render_template("driver/dashboard.html")
