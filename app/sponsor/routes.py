from flask import render_template, request, abort, redirect, url_for
from functools import wraps
from flask_login import current_user, login_required
from app.sponsor import sponsor_bp
from app.sponsor.services import update_sponsor_organization, create_sponsor_user
from app.extensions import db
from app.models import SponsorOrganization, SponsorUser, User
from app.models.enums import RoleType


def sponsor_required(f):
    '''Simple wrapper to ensure sponsor role for sponsor routes'''
    @wraps(f)
    def wrapper(*args, **kwargs):
        # impersonation logic may work well here
        if current_user.role_type != RoleType.SPONSOR:
            abort(403)
        return f(*args, **kwargs)
    return wrapper


@sponsor_bp.route('/dashboard')
@login_required
@sponsor_required
def dashboard():
    s_user: SponsorUser = current_user.sponsor_user
    sponsor_users = s_user.organization.sponsor_users
    users = [s.user for s in sponsor_users if s.sponsor_id != s_user.sponsor_id]
    return render_template('sponsor/dashboard.html', users=users)


@sponsor_bp.route('/organization', methods=['GET', 'POST'])
@login_required
@sponsor_required
def organization():
    org: SponsorOrganization = current_user.sponsor_user.organization
    if request.method == 'POST':
        name = request.form.get('name', '')
        point_value = request.form.get('point_value', '')
        try:
            org = update_sponsor_organization(org, name, point_value)
            return render_template('sponsor/organization.html', organization=org)
        except ValueError as e:
            return render_template('sponsor/organization.html', organization=org, error=str(e))

    return render_template('sponsor/organization.html', organization=org)


@sponsor_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
@sponsor_required
def profile_edit():
    assert isinstance(current_user, User)
    user: User = current_user

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip() or None

        if not username:
            return render_template('sponsor/profile_edit.html', user=user, error='Username is required.')

        existing_username = User.query.filter(User.username == username, User.user_id != user.user_id).first()
        if existing_username:
            return render_template('sponsor/profile_edit.html', user=user, error='Username is already in use.')

        if email:
            existing_email = User.query.filter(User.email == email, User.user_id != user.user_id).first()
            if existing_email:
                return render_template('sponsor/profile_edit.html', user=user, error='Email is already in use.')

        user.username = username
        user.email = email
        db.session.commit()
        return redirect(url_for('sponsor.profile_edit'))

    return render_template('sponsor/profile_edit.html', user=user)


@sponsor_bp.route('/create', methods=['GET', 'POST'])
@login_required
@sponsor_required
def create_user():
    fields = {'username': '', 'email': ''}

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        email = request.form.get('email', '').strip()
        fields = {'username': username, 'email': email}

        organization = current_user.sponsor_user.organization

        try:
            create_sponsor_user(username, password, email, organization)
        except ValueError as e:
            return render_template('sponsor/create_user.html', fields=fields, error=str(e))

        return redirect(url_for('auth.home'))

    return render_template('sponsor/create_user.html', fields=fields)
