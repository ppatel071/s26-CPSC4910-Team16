from flask import render_template, request, abort
from functools import wraps
from flask_login import current_user, login_required
from app.sponsor import sponsor_bp
from app.sponsor.services import update_sponsor_organization
from app.models import SponsorOrganization, SponsorUser
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
