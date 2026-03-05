import datetime as dt
from flask import render_template, request, abort, redirect, url_for
from functools import wraps
from flask_login import current_user, login_required
from app.sponsor import sponsor_bp
from app.sponsor.services import (
    update_sponsor_organization,
    create_sponsor_user,
    approve_driver_for_sponsor,
    get_driver_applications
)
from app.extensions import db
from app.models import SponsorOrganization, SponsorUser, User, DriverApplication
from app.models.enums import RoleType, DriverApplicationStatus


def sponsor_required(f):
    '''Simple wrapper to ensure sponsor role for sponsor routes'''
    @wraps(f)
    def wrapper(*args, **kwargs):
        # impersonation logic may work well here
        if current_user.role_type != RoleType.SPONSOR:
            abort(403)
        return f(*args, **kwargs)
    return wrapper

def sponsor_breadcrumbs(*crumbs):
    base = [("Sponsor Dashboard", url_for("sponsor.dashboard"))]
    return base + list(crumbs)

@sponsor_bp.route('/dashboard')
@login_required
@sponsor_required
def dashboard():
    s_user: SponsorUser = current_user.sponsor_user
    sponsor_users = s_user.organization.sponsor_users
    users = [s.user for s in sponsor_users if s.sponsor_id != s_user.sponsor_id]
    pending_applications, _ = get_driver_applications(current_user.sponsor_user.organization_id)
    if pending_applications is None:
        pending_applications = []
    num_applications = len(pending_applications)

    breadcrumbs = [("Sponsor Dashboard", None)]

    return render_template('sponsor/dashboard.html', users=users, num_applications=num_applications, breadcrumbs=breadcrumbs)


@sponsor_bp.route('/organization', methods=['GET', 'POST'])
@login_required
@sponsor_required
def organization():
    org: SponsorOrganization = current_user.sponsor_user.organization

    breadcrumbs = sponsor_breadcrumbs(("Organization", None))

    if request.method == 'POST':
        name = request.form.get('name', '')
        point_value = request.form.get('point_value', '')
        try:
            org = update_sponsor_organization(org, name, point_value)
            return render_template('sponsor/organization.html', organization=org, breadcrumbs=breadcrumbs)
        except ValueError as e:
            return render_template('sponsor/organization.html', organization=org, error=str(e), breadcrumbs=breadcrumbs)

    return render_template('sponsor/organization.html', organization=org, breadcrumbs=breadcrumbs)


@sponsor_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
@sponsor_required
def profile_edit():
    assert isinstance(current_user, User)
    user: User = current_user

    breadcrumbs = sponsor_breadcrumbs(("Edit Profile", None))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip() or None
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()

        if not username:
            return render_template('sponsor/profile_edit.html', user=user, error='Username is required.', breadcrumbs=breadcrumbs)

        existing_username = User.query.filter(User.username == username, User.user_id != user.user_id).first()
        if existing_username:
            return render_template('sponsor/profile_edit.html', user=user, error='Username is already in use.', breadcrumbs=breadcrumbs)

        if email:
            existing_email = User.query.filter(User.email == email, User.user_id != user.user_id).first()
            if existing_email:
                return render_template('sponsor/profile_edit.html', user=user, error='Email is already in use.', breadcrumbs=breadcrumbs)

        user.username = username
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        db.session.commit()
        return redirect(url_for('sponsor.profile_edit'))

    return render_template('sponsor/profile_edit.html', user=user, breadcrumbs=breadcrumbs)


@sponsor_bp.route('/create', methods=['GET', 'POST'])
@login_required
@sponsor_required
def create_user():
    fields = {'username': '', 'email': '', 'first_name': '', 'last_name': ''}

    breadcrumbs = sponsor_breadcrumbs(("Create Sponsor User", None))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        email = request.form.get('email', '').strip()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        fields = {
            'username': username,
            'email': email,
            'first_name': first_name,
            'last_name': last_name
        }

        organization = current_user.sponsor_user.organization

        try:
            create_sponsor_user(username, password, email, first_name, last_name, organization)
        except ValueError as e:
            return render_template('sponsor/create_user.html', fields=fields, error=str(e), breadcrumbs=breadcrumbs)

        return redirect(url_for('auth.home'))

    return render_template('sponsor/create_user.html', fields=fields, breadcrumbs=breadcrumbs)


@sponsor_bp.route('/applications')
@login_required
@sponsor_required
def get_applications():
    pending_applications, historic_applications = get_driver_applications(current_user.sponsor_user.organization_id)
    
    breadcrumbs = sponsor_breadcrumbs(("Applications", None))

    return render_template(
        'sponsor/driver_applications.html',
        pending_applications=pending_applications,
        historic_applications=historic_applications,
        breadcrumbs=breadcrumbs
    )


@sponsor_bp.route('/applications/<int:application_id>/decide', methods=['POST'])
@login_required
@sponsor_required
def decide_application(application_id: int):
    decision = (request.form.get('decision', '') or '').upper()
    reason = (request.form.get('reason', '') or '').strip()
    if decision not in ('APPROVED', 'REJECTED'):
        abort(400)

    application: DriverApplication | None = DriverApplication.query.get(application_id)

    if not application:
        abort(404)

    if application.status != DriverApplicationStatus.PENDING:
        return redirect(url_for('sponsor.get_applications'))

    decision = DriverApplicationStatus[decision]
    if decision == DriverApplicationStatus.APPROVED:
        approve_driver_for_sponsor(application.driver, current_user.sponsor_user.organization_id)

    application.status = decision
    application.reason = reason
    application.decision_date = dt.datetime.now(tz=dt.timezone.utc)
    application.decided_by_user_id = current_user.user_id
    db.session.commit()

    return redirect(url_for('sponsor.get_applications'))
