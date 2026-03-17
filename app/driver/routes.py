from functools import wraps
from typing import List, Tuple

from flask import abort, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from app.driver import driver_bp
from app.extensions import db
from app.models import (
    Driver,
    DriverApplication,
    DriverSponsorship,
    Order,
    PointTransaction,
    SponsorOrganization,
    User,
)
from app.models.enums import DriverApplicationStatus, DriverStatus, OrderStatus, RoleType

ACTIVE_SPONSORSHIP_SESSION_KEY = "active_driver_sponsorship_id"


def driver_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if current_user.role_type != RoleType.DRIVER:
            abort(403)
        return f(*args, **kwargs)

    return wrapper


def _get_active_sponsorships_for_driver(driver_id: int) -> List[DriverSponsorship]:
    return (
        DriverSponsorship.query
        .options(joinedload(DriverSponsorship.organization))
        .filter_by(driver_id=driver_id, status=DriverStatus.ACTIVE)
        .all()
    )


def _resolve_active_sponsorship(
    driver_id: int,
) -> Tuple[List[DriverSponsorship], DriverSponsorship | None]:
    sponsorships = _get_active_sponsorships_for_driver(driver_id)
    if not sponsorships:
        session.pop(ACTIVE_SPONSORSHIP_SESSION_KEY, None)
        return sponsorships, None

    requested_id = session.get(ACTIVE_SPONSORSHIP_SESSION_KEY)
    active_sponsorship = next(
        (s for s in sponsorships if s.driver_sponsorship_id == requested_id),
        None,
    )

    if active_sponsorship is None:
        sponsorships.sort(
            key=lambda s: (
                s.organization.name.lower() if s.organization else "",
                s.driver_sponsorship_id,
            )
        )
        active_sponsorship = sponsorships[0]
        session[ACTIVE_SPONSORSHIP_SESSION_KEY] = active_sponsorship.driver_sponsorship_id

    return sponsorships, active_sponsorship


def _get_available_organizations(
    driver_id: int,
    sponsored_organization_ids: set[int],
) -> list[SponsorOrganization]:
    pending_organization_ids = {
        application.organization_id
        for application in DriverApplication.query.filter_by(
            driver_id=driver_id,
            status=DriverApplicationStatus.PENDING,
        ).all()
    }
    excluded_ids = sponsored_organization_ids | pending_organization_ids

    query = SponsorOrganization.query.order_by(SponsorOrganization.name.asc())
    if excluded_ids:
        query = query.filter(~SponsorOrganization.organization_id.in_(excluded_ids))

    return query.all()


@driver_bp.context_processor
def inject_driver_context():
    driver = getattr(current_user, "driver", None) if current_user.is_authenticated else None
    if not driver:
        return {"driver_sponsorships": [], "active_sponsorship": None}

    sponsorships, active_sponsorship = _resolve_active_sponsorship(driver.driver_id)
    return {
        "driver_sponsorships": sponsorships,
        "active_sponsorship": active_sponsorship,
    }


@driver_bp.route("/dashboard")
@login_required
@driver_required
def dashboard():
    driver = current_user.driver
    assert isinstance(driver, Driver)

    sponsorships, active_sponsorship = _resolve_active_sponsorship(driver.driver_id)
    sponsored_organization_ids = {s.organization_id for s in sponsorships}
    available_organizations = _get_available_organizations(driver.driver_id, sponsored_organization_ids)

    transactions = []
    orders = []
    search_query = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip().upper()

    if active_sponsorship:
        transactions = (
            PointTransaction.query
            .filter_by(
                driver_id=driver.driver_id,
                organization_id=active_sponsorship.organization_id,
            )
            .order_by(PointTransaction.create_time.desc())
            .all()
        )
        orders = (
            Order.query
            .filter_by(
                driver_id=driver.driver_id,
                organization_id=active_sponsorship.organization_id,
            )
            .order_by(Order.create_time.desc())
            .all()
        )

    if search_query:
        orders = [order for order in orders if search_query.lower() in str(order.order_id).lower()]

    if status_filter:
        orders = [order for order in orders if order.order_status.value == status_filter]

    pending_applications = (
        DriverApplication.query
        .options(joinedload(DriverApplication.organization))
        .filter_by(driver_id=driver.driver_id, status=DriverApplicationStatus.PENDING)
        .order_by(DriverApplication.create_time.desc())
        .all()
    )

    return render_template(
        "driver/dashboard.html",
        active_sponsorship=active_sponsorship,
        available_organizations=available_organizations,
        orders=orders,
        pending_applications=pending_applications,
        search_query=search_query,
        status_filter=status_filter,
        transactions=transactions,
    )


@driver_bp.route("/application/submit", methods=["POST"])
@login_required
@driver_required
def submit_application():
    driver = current_user.driver
    assert isinstance(driver, Driver)

    organization_id = request.form.get("organization_id", type=int)
    full_name = (request.form.get("full_name") or "").strip()
    phone_number = (request.form.get("phone_number") or "").strip()
    address = (request.form.get("address") or "").strip()
    experience = (request.form.get("experience") or "").strip()

    if not organization_id or not full_name or not phone_number or not address or not experience:
        return redirect(url_for("driver.application_form", organization_id=organization_id))

    organization = SponsorOrganization.query.get_or_404(organization_id)
    active_sponsorships = _get_active_sponsorships_for_driver(driver.driver_id)
    if any(s.organization_id == organization.organization_id for s in active_sponsorships):
        return redirect(url_for("driver.dashboard"))

    available_organization_ids = {
        org.organization_id
        for org in _get_available_organizations(
            driver.driver_id,
            {s.organization_id for s in active_sponsorships},
        )
    }
    if organization.organization_id not in available_organization_ids:
        return redirect(url_for("driver.dashboard"))

    existing_pending_application = DriverApplication.query.filter_by(
        driver_id=driver.driver_id,
        organization_id=organization.organization_id,
        status=DriverApplicationStatus.PENDING,
    ).first()
    if existing_pending_application:
        return redirect(url_for("driver.dashboard"))

    application = DriverApplication(
        driver_id=driver.driver_id,
        organization_id=organization.organization_id,
        status=DriverApplicationStatus.PENDING,
        full_name=full_name,
        phone_number=phone_number,
        address=address,
        experience=experience,
    )
    db.session.add(application)
    db.session.commit()

    return redirect(url_for("driver.dashboard"))


@driver_bp.route("/account", methods=["GET", "POST"])
@login_required
def account_settings():
    user = current_user
    assert isinstance(user, User)

    if request.method == "POST":
        user.first_name = request.form.get("first_name", "").strip()
        user.last_name = request.form.get("last_name", "").strip()
        user.email = request.form.get("email", "").strip()

        db.session.commit()
        return redirect(url_for("driver.account_settings"))

    return render_template("driver/account_settings.html", user=user)


@driver_bp.route("/application")
@login_required
@driver_required
def application_form():
    driver = current_user.driver
    assert isinstance(driver, Driver)

    sponsorships, _ = _resolve_active_sponsorship(driver.driver_id)
    sponsored_organization_ids = {s.organization_id for s in sponsorships}
    available_organizations = _get_available_organizations(driver.driver_id, sponsored_organization_ids)
    selected_organization_id = request.args.get("organization_id", type=int)

    return render_template(
        "driver/application_form.html",
        available_organizations=available_organizations,
        selected_organization_id=selected_organization_id,
    )


@driver_bp.route("/set-active-sponsorship", methods=["POST"])
@login_required
@driver_required
def set_active_sponsorship():
    driver = current_user.driver
    if not driver:
        return redirect(url_for("driver.dashboard"))

    sponsorship_id_str = (request.form.get("driver_sponsorship_id") or "").strip()
    next_url = request.form.get("next") or url_for("driver.dashboard")
    sponsorships = _get_active_sponsorships_for_driver(driver.driver_id)

    if not sponsorships:
        session.pop(ACTIVE_SPONSORSHIP_SESSION_KEY, None)
        return redirect(next_url)

    try:
        sponsorship_id = int(sponsorship_id_str)
    except ValueError:
        return redirect(next_url)

    if any(s.driver_sponsorship_id == sponsorship_id for s in sponsorships):
        session[ACTIVE_SPONSORSHIP_SESSION_KEY] = sponsorship_id

    return redirect(next_url)


@driver_bp.route("/redeem", methods=["POST"])
@login_required
@driver_required
def redeem_points():
    driver = current_user.driver
    assert isinstance(driver, Driver)

    _, active_sponsorship = _resolve_active_sponsorship(driver.driver_id)
    if not active_sponsorship:
        return redirect(url_for("driver.dashboard"))

    return redirect(url_for("driver.dashboard"))


@driver_bp.route("/toggle-alert", methods=["POST"])
@login_required
@driver_required
def toggle_point_alert():
    driver = current_user.driver
    assert isinstance(driver, Driver)

    driver.point_change_alert = not driver.point_change_alert
    db.session.commit()
    return redirect(url_for("driver.dashboard"))


@driver_bp.route("/orders/<int:order_id>/cancel", methods=["POST"])
@login_required
@driver_required
def cancel_order(order_id: int):
    driver = current_user.driver
    assert isinstance(driver, Driver)

    order = Order.query.filter_by(order_id=order_id, driver_id=driver.driver_id).first()
    if not order or order.order_status == OrderStatus.CANCELLED:
        return redirect(url_for("driver.dashboard"))

    sponsorship = DriverSponsorship.query.filter_by(
        driver_id=driver.driver_id,
        organization_id=order.organization_id,
        status=DriverStatus.ACTIVE,
    ).first()
    if not sponsorship:
        return redirect(url_for("driver.dashboard"))

    order.order_status = OrderStatus.CANCELLED
    sponsorship.point_balance += order.points
    db.session.add(
        PointTransaction(
            driver_id=driver.driver_id,
            organization_id=order.organization_id,
            performed_by_user_id=current_user.user_id,
            point_change=order.points,
            reason=f"Order cancellation refund #{order.order_id}",
        )
    )
    db.session.commit()

    return redirect(url_for("driver.dashboard"))


@driver_bp.route("/apply/<int:organization_id>", methods=["POST"])
@login_required
@driver_required
def apply_to_organization(organization_id: int):
    return redirect(url_for("driver.application_form", organization_id=organization_id))


@driver_bp.route("/request-change/<int:organization_id>", methods=["POST"])
@login_required
@driver_required
def request_sponsor_change(organization_id: int):
    return redirect(url_for("driver.application_form", organization_id=organization_id))
