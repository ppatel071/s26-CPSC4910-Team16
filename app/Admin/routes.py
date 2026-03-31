import datetime as dt
from flask import render_template, abort, request, redirect, url_for
from functools import wraps
from flask_login import current_user, login_required
from app.Admin import admin_bp
from app.models.enums import RoleType
from app.models import User
from app.auth.services import register_user
from app.Admin.services import (
    get_all_sponsors,
    get_sponsor_by_id,
    admin_update_sponsor,
    get_sales_by_sponsor,
    get_sales_by_driver,
    get_driver_purchase_summary,
    get_all_admin_users,
    get_all_drivers,
    admin_update_driver_user,
    create_driver_account,
    admin_update_own_profile,
    get_all_sponsor_users,
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

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    breadcrumbs = [("Admin Dashboard", None)]

    return render_template('Admin/admin_dashboard.html', breadcrumbs=breadcrumbs)


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
    rows = get_sales_by_sponsor(detail)

    breadcrumbs = admin_breadcrumbs(("Reports", url_for("admin.reports")), ("Sales by Sponsor", None))

    return render_template('Admin/sales_by_sponsor.html', detail=detail, rows=rows, breadcrumbs=breadcrumbs)


@admin_bp.route('/reports/sales-by-driver')
@login_required
@admin_required
def sales_by_driver_report():
    detail = request.args.get('detail') == '1'
    rows = get_sales_by_driver(detail)

    breadcrumbs = admin_breadcrumbs(("Reports", url_for("admin.reports")), ("Sales by Driver", None))

    return render_template('Admin/sales_by_driver.html', detail=detail, rows=rows, breadcrumbs=breadcrumbs)


@admin_bp.route('/reports/driver-purchases-summary', methods=['GET'])
@login_required
@admin_required
def driver_purchases_summary():
    # Default to last 7 days if no dates provided
    today = dt.date.today()
    default_start = today - dt.timedelta(days=6)

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
            start_date=start_str,
            end_date=end_str,
            breadcrumbs=breadcrumbs
        )

    if end_date < start_date:
        return render_template(
            'Admin/driver_purchases_summary.html',
            error='End date must be on or after start date.',
            rows=[],
            start_date=start_str,
            end_date=end_str,
            breadcrumbs=breadcrumbs
        )
    rows = get_driver_purchase_summary(start_date, end_date)
    return render_template(
        'Admin/driver_purchases_summary.html',
        rows=rows,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        breadcrumbs=breadcrumbs
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
    users = get_all_admin_users()

    breadcrumbs = admin_breadcrumbs(("Admin Users", None))

    return render_template('Admin/admin_logins.html', users=users, breadcrumbs=breadcrumbs)


@admin_bp.route('/drivers')
@login_required
@admin_required
def drivers_list():
    drivers = get_all_drivers()
    message = request.args.get('message')

    breadcrumbs = admin_breadcrumbs(("Drivers", None))

    return render_template('Admin/drivers.html', drivers=drivers, breadcrumbs=breadcrumbs, message=message)


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
    rows = get_all_sponsor_users()

    breadcrumbs = admin_breadcrumbs(("Sponsor Users", None))

    return render_template('Admin/sponsor_users.html', rows=rows, breadcrumbs=breadcrumbs)

@admin_bp.route('/sponsors/new', methods=['GET', 'POST'])
@login_required
@admin_required
def create_sponsor_user():
    breadcrumbs = admin_breadcrumbs(("Sponsor Users", url_for("admin.sponsor_users_list")), ("Create Sponsor User",))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        organization_name = request.form.get('organization_name', '').strip()
        password = request.form.get('password', '')

        try:
            create_sponsor_account(
                username=username,
                email=email,
                organization_name=organization_name,
                password=password,
            )
            return redirect(url_for('admin.sponsor_users_list'))
        except ValueError as e:
            return render_template(
                'Admin/create_sponsor_user.html',
                error=str(e),
                username=username,
                email=email,
                organization_name=organization_name,
                breadcrumbs=breadcrumbs
            )

    return render_template('Admin/create_sponsor_user.html')


@admin_bp.route('/users/remove')
@login_required
@admin_required
def remove_users_page():
    admin_users, sponsor_users, driver_users = get_users_for_removal_page()
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
        breadcrumbs=breadcrumbs,
    )


@admin_bp.route('/users/drivers/<int:user_id>/deactivate', methods=['POST'])
@login_required
@admin_required
def deactivate_driver(user_id):
    try:
        deactivate_driver_user(user_id)
        return redirect(url_for('admin.remove_users_page', message='Driver user deactivated'))
    except ValueError as e:
        return redirect(url_for('admin.remove_users_page', error=str(e)))


@admin_bp.route('/users/drivers/<int:user_id>/reactivate', methods=['POST'])
@login_required
@admin_required
def reactivate_driver(user_id):
    try:
        reactivate_driver_user(user_id)
        return redirect(url_for('admin.remove_users_page', message='Driver user reactivated'))
    except ValueError as e:
        return redirect(url_for('admin.remove_users_page', error=str(e)))


@admin_bp.route('/users/admins/<int:user_id>/deactivate', methods=['POST'])
@login_required
@admin_required
def deactivate_admin(user_id):
    if current_user.user_id == user_id:
        return redirect(url_for('admin.remove_users_page', error='You cannot deactivate your own admin account'))
    try:
        deactivate_admin_user(user_id)
        return redirect(url_for('admin.remove_users_page', message='Admin user deactivated'))
    except ValueError as e:
        return redirect(url_for('admin.remove_users_page', error=str(e)))


@admin_bp.route('/users/admins/<int:user_id>/reactivate', methods=['POST'])
@login_required
@admin_required
def reactivate_admin(user_id):
    try:
        reactivate_admin_user(user_id)
        return redirect(url_for('admin.remove_users_page', message='Admin user reactivated'))
    except ValueError as e:
        return redirect(url_for('admin.remove_users_page', error=str(e)))


@admin_bp.route('/users/sponsors/<int:user_id>/deactivate', methods=['POST'])
@login_required
@admin_required
def deactivate_sponsor(user_id):
    try:
        deactivate_sponsor_user(user_id)
        return redirect(url_for('admin.remove_users_page', message='Sponsor user deactivated'))
    except ValueError as e:
        return redirect(url_for('admin.remove_users_page', error=str(e)))


@admin_bp.route('/users/sponsors/<int:user_id>/reactivate', methods=['POST'])
@login_required
@admin_required
def reactivate_sponsor(user_id):
    try:
        reactivate_sponsor_user(user_id)
        return redirect(url_for('admin.remove_users_page', message='Sponsor user reactivated'))
    except ValueError as e:
        return redirect(url_for('admin.remove_users_page', error=str(e)))


@admin_bp.route('/system-users')
@login_required
@admin_required
def system_users():
    users = get_all_system_users()
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
    )


@admin_bp.route('/audit-log/password-resets')
@login_required
@admin_required
def password_reset_audit_log():
    username = request.args.get('username', '').strip()
    entries = get_admin_password_reset_audit_entries(username=username)
    breadcrumbs = admin_breadcrumbs(("Password Reset Audit Log", None))
    return render_template(
        'Admin/password_reset_audit_log.html',
        entries=entries,
        username=username,
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
    try:
        unlock_user_login(user_id)
        return redirect(url_for('admin.system_users', message='User login lock removed'))
    except ValueError as e:
        return redirect(url_for('admin.system_users', error=str(e)))
