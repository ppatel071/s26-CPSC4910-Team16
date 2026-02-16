from flask import render_template, abort
from functools import wraps
from flask_login import current_user, login_required
from app.Admin import admin_bp
from app.models.users import RoleType
from app.Admin.services import get_all_sponsors

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if current_user.role_type != RoleType.ADMIN:
            abort(403)
        return f(*args, **kwargs)
    return wrapper

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    return render_template('Admin/admin_dashboard.html')

@admin_bp.route('/reports')
@login_required
@admin_required
def reports():
    sponsors = get_all_sponsors()
    return render_template('Admin/reports.html', sponsors=sponsors)


