import datetime as dt
import csv
from io import StringIO
from flask import render_template, abort, request, redirect, url_for, flash, Response
from functools import wraps
from flask_login import current_user, login_required
from flask_login import login_user
from app.Admin import admin_bp
from app.auth.impersonation import (
    start_admin_driver_impersonation,
    start_admin_sponsor_impersonation,
)
from app.bulk_upload import build_text_stream, process_bulk_upload_stream
from app.models.enums import RoleType, DriverStatus
from app.models import User, Driver, DriverSponsorship, SponsorOrganization
from app.auth.services import register_user
from app.extensions import db
from app.Admin.services import (
    get_all_sponsors,
    get_sponsor_by_id,
    admin_update_sponsor,
    get_sales_by_sponsor,
    get_sales_by_driver,
    get_driver_purchase_summary,
    get_invoice_report,
    format_money,
    get_all_admin_users,
    get_all_drivers,
    get_all_drivers_for_impersonation,
    count_active_sponsorships,
    get_driver_by_id,
    get_driver_for_impersonation,
    admin_update_driver_user,
    create_driver_account,
    admin_update_own_profile,
    get_all_sponsor_users,
    get_all_sponsor_users_for_impersonation,
    get_sponsor_user_for_impersonation,
    create_sponsor_account,
    get_users_for_removal_page,
    deactivate_driver_user,
    reactivate_driver_user,
    deactivate_admin_user,
    reactivate_admin_user,
    deactivate_sponsor_user,
    reactivate_sponsor_user,
    get_all_system_users,
    unlock_user_login,
    get_admin_password_reset_audit_entries,
    admin_reset_user_password,
    reassign_user_role,
    resolve_sponsor_organization_for_role_assignment,
    user_has_driver_dependencies,
    get_available_organizations,
)


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if current_user.role_type != RoleType.ADMIN:
            abort(403)
        return f(*args, **kwargs)
    return wrapper

def admin_breadcrumbs(*crumbs):
    base = [("Admin Dashboard", url_for("admin.dashboard"))]
    return base + list(crumbs)


def _build_user_display_name(user: User) -> str:
    name_parts = []
    for raw_part in [user.first_name, user.last_name]:
        clean_part = (raw_part or "").strip()
        if clean_part and clean_part.lower() != "none":
            name_parts.append(clean_part)

    display_name = " ".join(name_parts).strip()
    if display_name:
        return display_name
    return user.username


def _parse_optional_date(date_str: str) -> dt.date | None:
    clean_date = (date_str or "").strip()
    if not clean_date:
        return None
    return dt.date.fromisoformat(clean_date)


def render_bulk_upload_page(*, report=None, error: str | None = None):
    return render_template(
        'Admin/bulk_upload.html',
        report=report,
        error=error,
        breadcrumbs=admin_breadcrumbs(("Bulk Upload", None)),
    )

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    breadcrumbs = [("Admin Dashboard", None)]

    return render_template('Admin/admin_dashboard.html', breadcrumbs=breadcrumbs)


@admin_bp.route('/bulk-upload', methods=['GET', 'POST'])
@login_required
@admin_required
def bulk_upload():
    if request.method == 'POST':
        upload = request.files.get('bulk_upload_file')
        if upload is None or not upload.filename:
            return render_bulk_upload_page(error='Choose a pipe-delimited text file to upload.')

        try:
            stream = build_text_stream(upload)
            report = process_bulk_upload_stream(
                stream,
                acting_user=current_user,
                scope='admin',
            )
        except UnicodeDecodeError:
            return render_bulk_upload_page(error='The uploaded file must be UTF-8 text.')
        finally:
            if 'stream' in locals():
                stream.detach()

        return render_bulk_upload_page(report=report)

    return render_bulk_upload_page()


@admin_bp.route('/reports')
@login_required
@admin_required
def reports():
    sponsors = get_all_sponsors()

    breadcrumbs = admin_breadcrumbs(("Reports", None))

    return render_template('Admin/reports.html', sponsors=sponsors, breadcrumbs=breadcrumbs)


@admin_bp.route('/sponsors/<int:organization_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_sponsor(organization_id):
    try:
        org = get_sponsor_by_id(organization_id)
    except ValueError:
        abort(404)
    
    breadcrumbs = admin_breadcrumbs(("Reports", url_for("admin.reports")), ("Edit Sponsor", None))

    if request.method == 'POST':
        name = request.form.get('name', '')
        point_value = request.form.get('point_value', '')
        try:
            admin_update_sponsor(organization_id, name, point_value)
            return redirect(url_for('admin.reports'))
        except ValueError as e:
            return render_template('Admin/edit_sponsor.html', organization=org, error=str(e), breadcrumbs=breadcrumbs)

    return render_template('Admin/edit_sponsor.html', organization=org, breadcrumbs=breadcrumbs)


@admin_bp.route('/reports/sales-by-sponsor')
@login_required
@admin_required
def sales_by_sponsor_report():
    detail = request.args.get('detail') == '1'
    search = request.args.get('search', '').strip()
    start_str = request.args.get('start_date', '').strip()
    end_str = request.args.get('end_date', '').strip()

    start_date = None
    end_date = None
    error = None

    if detail:
        try:
            start_date = _parse_optional_date(start_str)
            end_date = _parse_optional_date(end_str)
        except ValueError:
            error = 'Invalid date format. Use YYYY-MM-DD.'

        if error is None and start_date and end_date and end_date < start_date:
            error = 'End date must be on or after start date.'

    rows = [] if error else get_sales_by_sponsor(
        detail,
        search=search,
        start_date=start_date,
        end_date=end_date,
    )

    breadcrumbs = admin_breadcrumbs(("Reports", url_for("admin.reports")), ("Sales by Sponsor", None))

    return render_template(
        'Admin/sales_by_sponsor.html',
        detail=detail,
        rows=rows,
        breadcrumbs=breadcrumbs,
        search=search,
        start_date=start_str,
        end_date=end_str,
        error=error,
    )

@admin_bp.route('reports/sales-by-sponsor/csv')
@login_required
@admin_required
def download_sales_by_sponsor_csv():
    detail = request.args.get('detail') == '1'
    search = request.args.get('search', '').strip()
    start_str = request.args.get('start_date', '').strip()
    end_str = request.args.get('end_date', '').strip()

    start_date = None
    end_date = None
    error = None

    if detail:
        try:
            start_date = _parse_optional_date(start_str)
            end_date = _parse_optional_date(end_str)
        except ValueError:
            error = 'Invalid date format. Use YYYY-MM-DD.'

        if error is None and start_date and end_date and end_date < start_date:
            error = 'End date must be on or after start date.'

    rows = [] if error else get_sales_by_sponsor(
        detail,
        search=search,
        start_date=start_date,
        end_date=end_date,
    )

    si = StringIO()
    writer = csv.writer(si)

    if detail:
        writer.writerow(["Sponsor", "Driver", "Amount (Points)", "Sale Time"])

        for row in rows:
            writer.writerow([
                row.sponsor_name,
                row.driver_username,
                row.amount,
                row.sale_time
            ])
    else:
        writer.writerow(["Sponsor", "Sales", "Total Amount (Points)"])

        for row in rows:
            writer.writerow([
                row.sponsor_name,
                row.sale_count,
                row.total_amount,
            ])
    
    output = si.getvalue()
    si.close

    return Response(
        output,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=sales_by_sponsor.csv"
        }
    )



@admin_bp.route('/reports/sales-by-driver')
@login_required
@admin_required
def sales_by_driver_report():
    detail = request.args.get('detail') == '1'
    search = request.args.get('search', '').strip()
    start_str = request.args.get('start_date', '').strip()
    end_str = request.args.get('end_date', '').strip()

    start_date = None
    end_date = None
    error = None

    if detail:
        try:
            start_date = _parse_optional_date(start_str)
            end_date = _parse_optional_date(end_str)
        except ValueError:
            error = 'Invalid date format. Use YYYY-MM-DD.'

        if error is None and start_date and end_date and end_date < start_date:
            error = 'End date must be on or after start date.'

    rows = [] if error else get_sales_by_driver(
        detail,
        search=search,
        start_date=start_date,
        end_date=end_date,
    )

    breadcrumbs = admin_breadcrumbs(("Reports", url_for("admin.reports")), ("Sales by Driver", None))

    return render_template(
        'Admin/sales_by_driver.html',
        detail=detail,
        rows=rows,
        breadcrumbs=breadcrumbs,
        search=search,
        start_date=start_str,
        end_date=end_str,
        error=error,
    )



@admin_bp.route('/reports/sales-by-driver/csv')
@login_required
@admin_required
def download_sales_by_driver_csv():
    detail = request.args.get('detail') == '1'
    search = request.args.get('search', '').strip()
    start_str = request.args.get('start_date', '').strip()
    end_str = request.args.get('end_date', '').strip()

    start_date = None
    end_date = None
    error = None

    if detail:
        try:
            start_date = _parse_optional_date(start_str)
            end_date = _parse_optional_date(end_str)
        except ValueError:
            error = 'Invalid date format. Use YYYY-MM-DD.'

        if error is None and start_date and end_date and end_date < start_date:
            error = 'End date must be on or after start date.'

    rows = [] if error else get_sales_by_driver(
        detail,
        search=search,
        start_date=start_date,
        end_date=end_date,
    )

    si = StringIO()
    writer = csv.writer(si)

    if detail:
        writer.writerow(["Driver", "Sponsor", "Amount (Points)", "Sale Time"])

        for row in rows:
            writer.writerow([
                row.driver_username,
                row.sponsor_name,
                row.amount,
                row.sale_time
            ])
    else:
        writer.writerow(["Driver", "Sales", "Total Amount (Points)"])

        for row in rows:
            writer.writerow([
                row.driver_username,
                row.sale_count,
                row.total_amount,
            ])
    
    output = si.getvalue()
    si.close

    return Response(
        output,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=sales_by_driver.csv"
        }
    )


@admin_bp.route('/reports/driver-purchases-summary', methods=['GET'])
@login_required
@admin_required
def driver_purchases_summary():
    # Default to last 7 days if no dates provided
    today = dt.date.today()
    default_start = today - dt.timedelta(days=6)

    search = request.args.get('search', '').strip()
    start_str = request.args.get('start_date') or default_start.isoformat()
    end_str = request.args.get('end_date') or today.isoformat()

    breadcrumbs = admin_breadcrumbs(("Reports", url_for("admin.reports")), ("Driver Purchase Summary", None))

    try:
        start_date = dt.date.fromisoformat(start_str)
        end_date = dt.date.fromisoformat(end_str)
    except ValueError:
        return render_template(
            'Admin/driver_purchases_summary.html',
            error='Invalid date format. Use YYYY-MM-DD.',
            rows=[],
            search=search,
            start_date=start_str,
            end_date=end_str,
            breadcrumbs=breadcrumbs
        )

    if end_date < start_date:
        return render_template(
            'Admin/driver_purchases_summary.html',
            error='End date must be on or after start date.',
            rows=[],
            search=search,
            start_date=start_str,
            end_date=end_str,
            breadcrumbs=breadcrumbs
        )
    rows = get_driver_purchase_summary(start_date, end_date, search=search)
    return render_template(
        'Admin/driver_purchases_summary.html',
        rows=rows,
        search=search,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        breadcrumbs=breadcrumbs
    )


@admin_bp.route('/reports/driver-purchases-summary/csv')
@login_required
@admin_required
def download_driver_purchase_summary_csv():
    today = dt.date.today()
    default_start = today - dt.timedelta(days=6)

    search = request.args.get('search', '').strip()
    start_str = request.args.get('start_date') or default_start.isoformat()
    end_str = request.args.get('end_date') or today.isoformat()

    start_date = dt.date.fromisoformat(start_str)
    end_date = dt.date.fromisoformat(end_str)

    rows = get_driver_purchase_summary(start_date, end_date, search=search)

    si = StringIO()
    writer = csv.writer(si)

    writer.writerow(["Driver", "Purchases", "Total Value (Points)"])

    for row in rows:
        writer.writerow([
            row.driver_username,
            row.purchase_count,
            row.total_amount,
        ])
    
    output = si.getvalue()
    si.close

    return Response(
        output,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=driver_purchase_summary.csv"
        }
    )




def _parse_invoice_filters():
    today = dt.date.today()
    default_start = today - dt.timedelta(days=6)

    sponsor_id_raw = (request.args.get('sponsor_id') or '').strip()
    search = request.args.get('search', '').strip()
    start_str = request.args.get('start_date') or default_start.isoformat()
    end_str = request.args.get('end_date') or today.isoformat()

    sponsor_id = None
    if sponsor_id_raw:
        try:
            sponsor_id = int(sponsor_id_raw)
        except ValueError:
            raise ValueError('Invalid sponsor selection.')

    try:
        start_date = dt.date.fromisoformat(start_str)
        end_date = dt.date.fromisoformat(end_str)
    except ValueError:
        raise ValueError('Invalid date format. Use YYYY-MM-DD.')

    if end_date < start_date:
        raise ValueError('End date must be on or after start date.')

    if sponsor_id is not None and SponsorOrganization.query.get(sponsor_id) is None:
        raise ValueError('Selected sponsor was not found.')

    return sponsor_id, sponsor_id_raw, search, start_date, end_date, start_str, end_str


@admin_bp.route('/reports/invoice')
@login_required
@admin_required
def invoice_report():
    sponsors = get_all_sponsors()
    breadcrumbs = admin_breadcrumbs(("Reports", url_for("admin.reports")), ("Invoice", None))
    error = None
    invoices = []

    try:
        sponsor_id, sponsor_id_raw, search, start_date, end_date, start_str, end_str = _parse_invoice_filters()
        invoices = get_invoice_report(
            sponsor_id=sponsor_id,
            start_date=start_date,
            end_date=end_date,
            search=search,
        )
    except ValueError as e:
        sponsor_id_raw = (request.args.get('sponsor_id') or '').strip()
        search = request.args.get('search', '').strip()
        start_str = request.args.get('start_date') or ''
        end_str = request.args.get('end_date') or ''
        error = str(e)

    return render_template(
        'Admin/invoice_report.html',
        sponsors=sponsors,
        invoices=invoices,
        selected_sponsor_id=sponsor_id_raw,
        search=search,
        start_date=start_str,
        end_date=end_str,
        invoice_date=dt.date.today().isoformat(),
        error=error,
        breadcrumbs=breadcrumbs,
        format_money=format_money,
    )

@admin_bp.route('/reports/invoice/csv')
@login_required
@admin_required
def download_invoice_report_csv():
    sponsors = get_all_sponsors()
    invoices = []


    sponsor_id, sponsor_id_raw, search, start_date, end_date, start_str, end_str = _parse_invoice_filters()
    invoices = get_invoice_report(
        sponsor_id=sponsor_id,
        start_date=start_date,
        end_date=end_date,
        search=search,
    )

    si = StringIO()
    writer = csv.writer(si)

    for invoice in invoices:
        sponsor = invoice['sponsor']

        writer.writerow(["Sponsor:", sponsor.name])

        writer.writerow([
            "Order ID",
            "Order Status",
            "Purchase Date",
            "Driver",
            "Product",
            "Quantity",
            "Purchase Amount",
            "Fee Amount",
            ])

        for row in invoice['detail_rows']:
            writer.writerow([
                row['order_id'],
                row['order_status'],
                row['purchase_date'].strftime('%Y-%m-%d'),
                row['driver_name'],
                row['product_name'],
                row['quantity'],
                row['purchase_amount'],
                row['fee_amount'],
            ])
        
        writer.writerow(["", "", "", "", "", "", "Total Fee:", str(invoice['total_fee_due'])])

        writer.writerow([])
        writer.writerow([])
    
    output = si.getvalue()
    si.close()

    return Response(
        output,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=Invoice_Report.csv"
        }
    )


@admin_bp.route('/profile')
@login_required
@admin_required
def profile():
    breadcrumbs = admin_breadcrumbs(("Profile", None))

    return render_template('Admin/admin_profile.html', user=current_user, breadcrumbs=breadcrumbs)


@admin_bp.route('/admin-users')
@login_required
@admin_required
def admin_logins():
    username = request.args.get('username', '').strip()
    users = get_all_admin_users(username=username)

    breadcrumbs = admin_breadcrumbs(("Admin Users", None))

    return render_template(
        'Admin/admin_logins.html',
        users=users,
        breadcrumbs=breadcrumbs,
        username=username,
    )


@admin_bp.route('/drivers')
@login_required
@admin_required
def drivers_list():
    username = request.args.get('username', '').strip()
    drivers_query = (
        db.session.query(User, Driver)
        .join(Driver, Driver.user_id == User.user_id)
        .order_by(User.username.asc())
    )
    if username:
        drivers_query = drivers_query.filter(User.username.ilike(f'%{username}%'))

    drivers = drivers_query.all()
    message = request.args.get('message')
    error = request.args.get('error')

    driver_orgs = {}
    driver_sponsors = {}
    for user, driver in drivers:
        driver_orgs[user.user_id] = get_available_organizations(driver.driver_id)

        active_sponsors = (
            db.session.query(SponsorOrganization)
            .join(
                DriverSponsorship,
                DriverSponsorship.organization_id == SponsorOrganization.organization_id,
            )
            .filter(
                DriverSponsorship.driver_id == driver.driver_id,
                DriverSponsorship.status == DriverStatus.ACTIVE,
            )
            .order_by(SponsorOrganization.name.asc())
            .all()
        )

        driver_sponsors[user.user_id] = active_sponsors

    breadcrumbs = admin_breadcrumbs(("Drivers", None))

    return render_template(
        'Admin/drivers.html',
        drivers=drivers,
        breadcrumbs=breadcrumbs,
        message=message,
        error=error,
        driver_orgs=driver_orgs,
        driver_sponsors=driver_sponsors,
        username=username,
    )

@admin_bp.route('/drivers/<int:user_id>/add-to-sponsor', methods=['POST'])
@login_required
@admin_required
def add_driver_to_sponsor(user_id):
    organization_id = request.form.get('organization_id', type=int)
    if not organization_id:
        return redirect(url_for('admin.drivers_list', error='Please select a sponsor organization'))
    
    driver = Driver.query.filter_by(user_id=user_id).first()

    if not driver:
        return redirect(url_for('admin.drivers_list', error='Driver not found'))
    
    existing = DriverSponsorship.query.filter_by(driver_id=driver.driver_id, organization_id=organization_id).first()

    if existing:
        return redirect(url_for('admin.drivers_list', error='Driver is already sponsored by this organization'))
    
    sponsorship = DriverSponsorship(driver_id=driver.driver_id, organization_id=organization_id, status=DriverStatus.ACTIVE)

    db.session.add(sponsorship)
    db.session.commit()

    return redirect(url_for('admin.drivers_list', message='Driver added to sponsor organization successfully'))

@admin_bp.route('/drivers/impersonate')
@login_required
@admin_required
def impersonate_driver_page():
    username = request.args.get('username', '').strip()
    driver_rows = [
        {
            "user": user,
            "active_sponsorship_count": count_active_sponsorships(user.driver),
            "total_sponsorship_count": len(user.driver.sponsorships),
        }
        for user in get_all_drivers_for_impersonation(username=username)
    ]
    breadcrumbs = admin_breadcrumbs(("Drivers", url_for("admin.drivers_list")), ("Impersonate Driver", None))
    return render_template(
        'Admin/impersonate_driver.html',
        driver_rows=driver_rows,
        breadcrumbs=breadcrumbs,
        username=username,
    )


@admin_bp.route('/drivers/<int:user_id>/impersonate', methods=['POST'])
@login_required
@admin_required
def impersonate_driver(user_id):
    try:
        driver_user = get_driver_for_impersonation(user_id)
    except ValueError:
        abort(404)

    admin_user_id = current_user.user_id

    start_admin_driver_impersonation(admin_user_id)
    login_user(driver_user)

    display_name = _build_user_display_name(driver_user)
    flash(f"You are now impersonating {display_name}.", "success")
    return redirect(url_for('driver.dashboard'))


@admin_bp.route('/drivers/new', methods=['GET', 'POST'])
@login_required
@admin_required
def create_driver_user():
    breadcrumbs = admin_breadcrumbs(("Drivers", url_for("admin.drivers_list")), ("Add Driver", None))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        password = request.form.get('password', '')
        confpass = request.form.get('confpass', '')

        try:
            create_driver_account(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=password,
                confpass=confpass,
            )
            return redirect(url_for('admin.drivers_list', message='Driver user created'))
        except ValueError as e:
            return render_template(
                'Admin/create_driver_user.html',
                error=str(e),
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                breadcrumbs=breadcrumbs,
            )

    return render_template('Admin/create_driver_user.html', breadcrumbs=breadcrumbs)


@admin_bp.route('/drivers/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_driver(user_id):
    if request.method == 'POST':
        username = request.form.get('username', '')
        email = request.form.get('email', '')
        first_name = request.form.get('first_name', '')
        last_name = request.form.get('last_name', '')
        try:
            admin_update_driver_user(user_id, username, email, first_name, last_name)
            return redirect(url_for('admin.drivers_list', message='Driver user updated'))
        except ValueError as e:
            drivers = get_all_drivers()
            breadcrumbs = admin_breadcrumbs(("Drivers", None))
            return render_template('Admin/drivers.html', drivers=drivers, error=str(e), breadcrumbs=breadcrumbs)

    return redirect(url_for('admin.drivers_list'))


@admin_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_profile():
    assert isinstance(current_user, User)
    user: User = current_user

    if request.method == 'POST':
        username = request.form.get('username', '')
        email = request.form.get('email', '')
        first_name = request.form.get('first_name', '')
        last_name = request.form.get('last_name', '')

        try:
            admin_update_own_profile(user, username, email, first_name, last_name)
            return redirect(url_for('admin.profile'))
        except ValueError as e:
            return render_template('Admin/edit_profile.html', user=user, error=str(e))

    return render_template('Admin/edit_profile.html', user=user)


@admin_bp.route('/admin-users/new', methods=['GET', 'POST'])
@login_required
@admin_required
def create_admin_user():
    breadcrumbs = admin_breadcrumbs(("Admin Users", url_for("admin.admin_logins")), ("Create Admin User", None))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        password = request.form.get('password', '')
        confpass = request.form.get('confpass', '')

        try:
            register_user(
                username=username,
                password=password,
                role=RoleType.ADMIN,
                email=email,
                first_name=first_name,
                last_name=last_name,
                confpass=confpass,
            )
            return redirect(url_for('admin.admin_logins'))
        except ValueError as e:
            return render_template(
                'Admin/create_admin_user.html',
                error=str(e),
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                breadcrumbs=breadcrumbs
            )

    return render_template('Admin/create_admin_user.html')

@admin_bp.route('/sponsors/users')
@login_required
@admin_required
def sponsor_users_list():
    username = request.args.get('username', '').strip()
    rows = get_all_sponsor_users(username=username)

    breadcrumbs = admin_breadcrumbs(("Sponsor Users", None))

    return render_template(
        'Admin/sponsor_users.html',
        rows=rows,
        breadcrumbs=breadcrumbs,
        username=username,
    )


@admin_bp.route('/sponsors/impersonate')
@login_required
@admin_required
def impersonate_sponsor_page():
    username = request.args.get('username', '').strip()
    sponsor_users = get_all_sponsor_users_for_impersonation(username=username)
    breadcrumbs = admin_breadcrumbs(
        ("Sponsor Users", url_for("admin.sponsor_users_list")),
        ("Impersonate Sponsor", None),
    )
    return render_template(
        'Admin/impersonate_sponsor.html',
        sponsor_users=sponsor_users,
        breadcrumbs=breadcrumbs,
        username=username,
    )


@admin_bp.route('/sponsors/<int:user_id>/impersonate', methods=['POST'])
@login_required
@admin_required
def impersonate_sponsor(user_id):
    try:
        sponsor_user = get_sponsor_user_for_impersonation(user_id)
    except ValueError:
        abort(404)

    admin_user_id = current_user.user_id

    start_admin_sponsor_impersonation(admin_user_id)
    login_user(sponsor_user)

    display_name = _build_user_display_name(sponsor_user)
    flash(f"You are now impersonating {display_name}.", "success")
    return redirect(url_for('sponsor.dashboard'))


@admin_bp.route('/sponsors/new', methods=['GET', 'POST'])
@login_required
@admin_required
def create_sponsor_user():
    breadcrumbs = admin_breadcrumbs(("Sponsor Users", url_for("admin.sponsor_users_list")), ("Create Sponsor User", None))
    sponsors = get_all_sponsors()

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        sponsor_organization_id_raw = request.form.get('sponsor_organization_id', '').strip()
        new_sponsor_organization_name = request.form.get('new_sponsor_organization_name', '').strip()
        password = request.form.get('password', '')
        confpass = request.form.get('confpass', '')

        try:
            sponsor_organization_id = int(sponsor_organization_id_raw) if sponsor_organization_id_raw else None
            create_sponsor_account(
                username=username,
                email=email,
                sponsor_organization_id=sponsor_organization_id,
                new_sponsor_organization_name=new_sponsor_organization_name,
                password=password,
                confpass=confpass,
            )
            return redirect(url_for('admin.sponsor_users_list'))
        except ValueError as e:
            return render_template(
                'Admin/create_sponsor_user.html',
                error=str(e),
                username=username,
                email=email,
                sponsors=sponsors,
                selected_sponsor_organization_id=(
                    int(sponsor_organization_id_raw) if sponsor_organization_id_raw.isdigit() else None
                ),
                new_sponsor_organization_name=new_sponsor_organization_name,
                breadcrumbs=breadcrumbs,
            )

    return render_template(
        'Admin/create_sponsor_user.html',
        sponsors=sponsors,
        selected_sponsor_organization_id=None,
        new_sponsor_organization_name='',
        breadcrumbs=breadcrumbs,
    )


@admin_bp.route('/users/remove')
@login_required
@admin_required
def remove_users_page():
    admin_username = request.args.get('admin_username', '').strip()
    sponsor_username = request.args.get('sponsor_username', '').strip()
    driver_username = request.args.get('driver_username', '').strip()
    admin_users, sponsor_users, driver_users = get_users_for_removal_page(
        admin_username=admin_username,
        sponsor_username=sponsor_username,
        driver_username=driver_username,
    )
    breadcrumbs = admin_breadcrumbs(("Remove Users", None))
    message = request.args.get('message')
    error = request.args.get('error')

    return render_template(
        'Admin/remove_users.html',
        admin_users=admin_users,
        sponsor_users=sponsor_users,
        driver_users=driver_users,
        message=message,
        error=error,
        search_admin_username=admin_username,
        search_sponsor_username=sponsor_username,
        search_driver_username=driver_username,
        breadcrumbs=breadcrumbs,
    )


@admin_bp.route('/users/drivers/<int:user_id>/deactivate', methods=['POST'])
@login_required
@admin_required
def deactivate_driver(user_id):
    admin_username = request.args.get('admin_username', '').strip()
    sponsor_username = request.args.get('sponsor_username', '').strip()
    driver_username = request.args.get('driver_username', '').strip()
    try:
        deactivate_driver_user(user_id)
        return redirect(url_for(
            'admin.remove_users_page',
            message='Driver user deactivated',
            admin_username=admin_username,
            sponsor_username=sponsor_username,
            driver_username=driver_username,
        ))
    except ValueError as e:
        return redirect(url_for(
            'admin.remove_users_page',
            error=str(e),
            admin_username=admin_username,
            sponsor_username=sponsor_username,
            driver_username=driver_username,
        ))


@admin_bp.route('/users/drivers/<int:user_id>/reactivate', methods=['POST'])
@login_required
@admin_required
def reactivate_driver(user_id):
    admin_username = request.args.get('admin_username', '').strip()
    sponsor_username = request.args.get('sponsor_username', '').strip()
    driver_username = request.args.get('driver_username', '').strip()
    try:
        reactivate_driver_user(user_id)
        return redirect(url_for(
            'admin.remove_users_page',
            message='Driver user reactivated',
            admin_username=admin_username,
            sponsor_username=sponsor_username,
            driver_username=driver_username,
        ))
    except ValueError as e:
        return redirect(url_for(
            'admin.remove_users_page',
            error=str(e),
            admin_username=admin_username,
            sponsor_username=sponsor_username,
            driver_username=driver_username,
        ))


@admin_bp.route('/users/admins/<int:user_id>/deactivate', methods=['POST'])
@login_required
@admin_required
def deactivate_admin(user_id):
    admin_username = request.args.get('admin_username', '').strip()
    sponsor_username = request.args.get('sponsor_username', '').strip()
    driver_username = request.args.get('driver_username', '').strip()
    if current_user.user_id == user_id:
        return redirect(url_for(
            'admin.remove_users_page',
            error='You cannot deactivate your own admin account',
            admin_username=admin_username,
            sponsor_username=sponsor_username,
            driver_username=driver_username,
        ))
    try:
        deactivate_admin_user(user_id)
        return redirect(url_for(
            'admin.remove_users_page',
            message='Admin user deactivated',
            admin_username=admin_username,
            sponsor_username=sponsor_username,
            driver_username=driver_username,
        ))
    except ValueError as e:
        return redirect(url_for(
            'admin.remove_users_page',
            error=str(e),
            admin_username=admin_username,
            sponsor_username=sponsor_username,
            driver_username=driver_username,
        ))


@admin_bp.route('/users/admins/<int:user_id>/reactivate', methods=['POST'])
@login_required
@admin_required
def reactivate_admin(user_id):
    admin_username = request.args.get('admin_username', '').strip()
    sponsor_username = request.args.get('sponsor_username', '').strip()
    driver_username = request.args.get('driver_username', '').strip()
    try:
        reactivate_admin_user(user_id)
        return redirect(url_for(
            'admin.remove_users_page',
            message='Admin user reactivated',
            admin_username=admin_username,
            sponsor_username=sponsor_username,
            driver_username=driver_username,
        ))
    except ValueError as e:
        return redirect(url_for(
            'admin.remove_users_page',
            error=str(e),
            admin_username=admin_username,
            sponsor_username=sponsor_username,
            driver_username=driver_username,
        ))


@admin_bp.route('/users/sponsors/<int:user_id>/deactivate', methods=['POST'])
@login_required
@admin_required
def deactivate_sponsor(user_id):
    admin_username = request.args.get('admin_username', '').strip()
    sponsor_username = request.args.get('sponsor_username', '').strip()
    driver_username = request.args.get('driver_username', '').strip()
    try:
        deactivate_sponsor_user(user_id)
        return redirect(url_for(
            'admin.remove_users_page',
            message='Sponsor user deactivated',
            admin_username=admin_username,
            sponsor_username=sponsor_username,
            driver_username=driver_username,
        ))
    except ValueError as e:
        return redirect(url_for(
            'admin.remove_users_page',
            error=str(e),
            admin_username=admin_username,
            sponsor_username=sponsor_username,
            driver_username=driver_username,
        ))


@admin_bp.route('/users/sponsors/<int:user_id>/reactivate', methods=['POST'])
@login_required
@admin_required
def reactivate_sponsor(user_id):
    admin_username = request.args.get('admin_username', '').strip()
    sponsor_username = request.args.get('sponsor_username', '').strip()
    driver_username = request.args.get('driver_username', '').strip()
    try:
        reactivate_sponsor_user(user_id)
        return redirect(url_for(
            'admin.remove_users_page',
            message='Sponsor user reactivated',
            admin_username=admin_username,
            sponsor_username=sponsor_username,
            driver_username=driver_username,
        ))
    except ValueError as e:
        return redirect(url_for(
            'admin.remove_users_page',
            error=str(e),
            admin_username=admin_username,
            sponsor_username=sponsor_username,
            driver_username=driver_username,
        ))


@admin_bp.route('/system-users')
@login_required
@admin_required
def system_users():
    username = request.args.get('username', '').strip()
    users = get_all_system_users(username=username)
    breadcrumbs = admin_breadcrumbs(("System Users", None))
    message = request.args.get('message')
    error = request.args.get('error')
    return render_template(
        'Admin/system_users.html',
        users=users,
        RoleType=RoleType,
        breadcrumbs=breadcrumbs,
        message=message,
        error=error,
        search_username=username,
    )


@admin_bp.route('/users/<int:user_id>/role', methods=['GET', 'POST'])
@login_required
@admin_required
def assign_user_role(user_id):
    user = User.query.get_or_404(user_id)
    breadcrumbs = admin_breadcrumbs(
        ("System Users", url_for("admin.system_users")),
        ("Assign User Role", None),
    )
    sponsors = get_all_sponsors()
    role_options = [RoleType.ADMIN, RoleType.SPONSOR, RoleType.DRIVER]

    if request.method == 'POST':
        selected_role = request.form.get('role_type', '').strip()
        sponsor_organization_id = request.form.get('sponsor_organization_id', type=int)
        new_sponsor_organization_name = request.form.get('new_sponsor_organization_name', '').strip()

        if selected_role == RoleType.SPONSOR.value:
            try:
                sponsor_organization_id = resolve_sponsor_organization_for_role_assignment(
                    sponsor_organization_id,
                    new_sponsor_organization_name,
                )
            except ValueError as e:
                return render_template(
                    'Admin/assign_user_role.html',
                    user=user,
                    sponsors=sponsors,
                    role_options=role_options,
                    selected_role=selected_role,
                    selected_sponsor_organization_id=request.form.get('sponsor_organization_id', ''),
                    new_sponsor_organization_name=new_sponsor_organization_name,
                    has_driver_dependencies=user_has_driver_dependencies(user),
                    error=str(e),
                    breadcrumbs=breadcrumbs,
                )

        if current_user.user_id == user.user_id and selected_role != RoleType.ADMIN.value:
            return render_template(
                'Admin/assign_user_role.html',
                user=user,
                sponsors=sponsors,
                role_options=role_options,
                selected_role=selected_role,
                selected_sponsor_organization_id=sponsor_organization_id,
                new_sponsor_organization_name=new_sponsor_organization_name,
                has_driver_dependencies=user_has_driver_dependencies(user),
                error='You cannot change your own admin account to a different role.',
                breadcrumbs=breadcrumbs,
            )

        try:
            reassign_user_role(user.user_id, selected_role, sponsor_organization_id)
            return redirect(
                url_for(
                    'admin.system_users',
                    message=f'Role updated for user {user.username}'
                )
            )
        except ValueError as e:
            return render_template(
                'Admin/assign_user_role.html',
                user=user,
                sponsors=sponsors,
                role_options=role_options,
                selected_role=selected_role,
                selected_sponsor_organization_id=sponsor_organization_id,
                new_sponsor_organization_name=new_sponsor_organization_name,
                has_driver_dependencies=user_has_driver_dependencies(user),
                error=str(e),
                breadcrumbs=breadcrumbs,
            )

    return render_template(
        'Admin/assign_user_role.html',
        user=user,
        sponsors=sponsors,
        role_options=role_options,
        selected_role=user.role_type.value,
        selected_sponsor_organization_id=(
            user.sponsor_user.organization_id if user.sponsor_user else None
        ),
        new_sponsor_organization_name='',
        has_driver_dependencies=user_has_driver_dependencies(user),
        breadcrumbs=breadcrumbs,
    )


@admin_bp.route('/audit-log/password-resets')
@login_required
@admin_required
def password_reset_audit_log():
    username = request.args.get('username', '').strip()
    start_date_str = request.args.get('start_date', '').strip()
    end_date_str = request.args.get('end_date', '').strip()
    breadcrumbs = admin_breadcrumbs(("Password Reset Audit Log", None))

    try:
        start_date = dt.date.fromisoformat(start_date_str) if start_date_str else None
        end_date = dt.date.fromisoformat(end_date_str) if end_date_str else None
    except ValueError:
        return render_template(
            'Admin/password_reset_audit_log.html',
            entries=[],
            username=username,
            start_date=start_date_str,
            end_date=end_date_str,
            error='Invalid date format. Use YYYY-MM-DD.',
            breadcrumbs=breadcrumbs,
        )

    if start_date and end_date and end_date < start_date:
        return render_template(
            'Admin/password_reset_audit_log.html',
            entries=[],
            username=username,
            start_date=start_date_str,
            end_date=end_date_str,
            error='End date must be on or after start date.',
            breadcrumbs=breadcrumbs,
        )

    entries = get_admin_password_reset_audit_entries(
        username=username,
        start_date=start_date,
        end_date=end_date,
    )
    return render_template(
        'Admin/password_reset_audit_log.html',
        entries=entries,
        username=username,
        start_date=start_date_str,
        end_date=end_date_str,
        breadcrumbs=breadcrumbs,
    )


@admin_bp.route('/users/<int:user_id>/password-reset', methods=['GET', 'POST'])
@login_required
@admin_required
def reset_user_password_as_admin(user_id):
    user = User.query.get_or_404(user_id)
    breadcrumbs = admin_breadcrumbs(
        ("System Users", url_for("admin.system_users")),
        ("Reset User Password", None),
    )

    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        try:
            admin_reset_user_password(user.user_id, new_password, confirm_password)
            return redirect(
                url_for(
                    'admin.system_users',
                    message=f'Password updated for user {user.username}'
                )
            )
        except ValueError as e:
            return render_template(
                'Admin/admin_reset_user_password.html',
                user=user,
                error=str(e),
                breadcrumbs=breadcrumbs,
            )

    return render_template(
        'Admin/admin_reset_user_password.html',
        user=user,
        breadcrumbs=breadcrumbs,
    )


@admin_bp.route('/users/<int:user_id>/unlock', methods=['POST'])
@login_required
@admin_required
def unlock_locked_user(user_id):
    username = request.args.get('username', '').strip()
    try:
        unlock_user_login(user_id)
        return redirect(url_for('admin.system_users', message='User login lock removed', username=username))
    except ValueError as e:
        return redirect(url_for('admin.system_users', error=str(e), username=username))
