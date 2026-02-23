import datetime as dt
from flask import render_template, abort, request, redirect, url_for
from functools import wraps
from flask_login import current_user, login_required
from app.Admin import admin_bp
from app.models.enums import RoleType
from app.Admin.services import (
    get_all_sponsors,
    get_sponsor_by_id,
    admin_update_sponsor,
    get_sales_by_sponsor,
    get_sales_by_driver,
    get_driver_purchase_summary,
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
        try:
            admin_update_sponsor(organization_id, name)
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


@admin_bp.route('/reports/driver-purchases-summary', methods=['GET'])
@login_required
@admin_required
def driver_purchases_summary():
    # Default to last 7 days if no dates provided
    today = dt.date.today()
    default_start = today - dt.timedelta(days=6)

    start_str = request.args.get('start_date') or default_start.isoformat()
    end_str = request.args.get('end_date') or today.isoformat()

    try:
        start_date = dt.date.fromisoformat(start_str)
        end_date = dt.date.fromisoformat(end_str)
    except ValueError:
        return render_template(
            'Admin/driver_purchases_summary.html',
            error='Invalid date format. Use YYYY-MM-DD.',
            rows=[],
            start_date=start_str,
            end_date=end_str,
        )

    if end_date < start_date:
        return render_template(
            'Admin/driver_purchases_summary.html',
            error='End date must be on or after start date.',
            rows=[],
            start_date=start_str,
            end_date=end_str,
        )
    rows = get_driver_purchase_summary(start_date, end_date)
    return render_template(
        'Admin/driver_purchases_summary.html',
        rows=rows,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
    )
