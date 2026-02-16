from flask import render_template, abort, request, redirect, url_for
from functools import wraps
from flask_login import current_user, login_required
from app.Admin import admin_bp
from app.models.users import RoleType
from app.Admin.services import (
    get_all_sponsors,
    get_sponsor_by_id,
    admin_update_sponsor,
    get_sales_by_sponsor,
    get_sales_by_driver,
)

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

@admin_bp.route('/sponsors/<int:organization_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_sponsor(organization_id):
    org = get_sponsor_by_id(organization_id)
    if not org:
        abort(404)

    if request.method == 'POST':
        name = request.form.get('name', '')
        point_value = request.form.get('point_value', '')
        try:
            admin_update_sponsor(organization_id, name, point_value)
            return redirect(url_for('admin.reports'))
        except ValueError as e:
            return render_template('Admin/edit_sponsor.html', organization=org, error=str(e))

    return render_template('Admin/edit_sponsor.html', organization=org)


@admin_bp.route('/reports/sales-by-sponsor')
@login_required
@admin_required
def sales_by_sponsor_report():
    detail = request.args.get('detail') == '1'
    rows = get_sales_by_sponsor(detail)
    return render_template('Admin/sales_by_sponsor.html', detail=detail, rows=rows)


@admin_bp.route('/reports/sales-by-driver')
@login_required
@admin_required
def sales_by_driver_report():
    detail = request.args.get('detail') == '1'
    rows = get_sales_by_driver(detail)
    return render_template('Admin/sales_by_driver.html', detail=detail, rows=rows)

