from __future__ import annotations

from flask import session
from sqlalchemy.orm import joinedload

from app.auth.impersonation import (
    get_impersonated_driver_sponsorship_id,
    get_impersonator_sponsor_user_id,
    is_sponsor_driver_impersonation_active,
)
from app.extensions import db
from app.models import (
    Driver,
    DriverApplication,
    DriverSponsorship,
    Notification,
    Order,
    OrderItem,
    PointTransaction,
    SponsorOrganization,
    User,
)
from app.models.enums import (
    DriverApplicationStatus,
    DriverStatus,
    NotificationCategory,
    OrderStatus,
    RoleType,
)
from app.models.organization import SponsorCatalogItem

ACTIVE_SPONSORSHIP_SESSION_KEY = "active_driver_sponsorship_id"


def get_active_sponsorships_for_driver(driver_id: int) -> list[DriverSponsorship]:
    return (
        DriverSponsorship.query.options(joinedload(DriverSponsorship.organization))
        .filter_by(driver_id=driver_id, status=DriverStatus.ACTIVE)
        .all()
    )


def resolve_active_sponsorship(
    driver_id: int,
) -> tuple[list[DriverSponsorship], DriverSponsorship | None]:
    sponsorships = get_active_sponsorships_for_driver(driver_id)
    forced_sponsorship_id = get_impersonated_driver_sponsorship_id()

    if forced_sponsorship_id is not None:
        sponsorships = [
            sponsorship
            for sponsorship in sponsorships
            if sponsorship.driver_sponsorship_id == forced_sponsorship_id
        ]
        if not sponsorships:
            session.pop(ACTIVE_SPONSORSHIP_SESSION_KEY, None)
            return sponsorships, None

        active_sponsorship = sponsorships[0]
        session[ACTIVE_SPONSORSHIP_SESSION_KEY] = active_sponsorship.driver_sponsorship_id
        return sponsorships, active_sponsorship

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


def get_active_sponsorship(driver: Driver) -> DriverSponsorship | None:
    _, active_sponsorship = resolve_active_sponsorship(driver.driver_id)
    return active_sponsorship


def get_available_organizations(driver_id: int) -> list[SponsorOrganization]:
    active_sponsorship_orgs = db.session.query(DriverSponsorship.organization_id).filter(
        DriverSponsorship.driver_id == driver_id,
        DriverSponsorship.status == DriverStatus.ACTIVE,
    )
    pending_application_orgs = db.session.query(DriverApplication.organization_id).filter(
        DriverApplication.driver_id == driver_id,
        DriverApplication.status == DriverApplicationStatus.PENDING,
    )

    return (
        SponsorOrganization.query.filter(
            ~SponsorOrganization.organization_id.in_(active_sponsorship_orgs)
        )
        .filter(~SponsorOrganization.organization_id.in_(pending_application_orgs))
        .order_by(SponsorOrganization.name.asc())
        .all()
    )


def is_driver_impersonated() -> bool:
    return is_sponsor_driver_impersonation_active()


def get_impersonating_sponsor_user() -> User | None:
    sponsor_user_id = get_impersonator_sponsor_user_id()
    if sponsor_user_id is None:
        return None
    return User.query.get(sponsor_user_id)


def build_impersonation_banner_context() -> dict[str, str | bool | None]:
    banner_message = None
    if is_driver_impersonated():
        sponsor_user = get_impersonating_sponsor_user()
        sponsor_name = (
            sponsor_user.sponsor_user.organization.name
            if sponsor_user and sponsor_user.sponsor_user and sponsor_user.sponsor_user.organization
            else None
        )
        banner_message = "You are impersonating this user"
        if sponsor_name:
            banner_message += f" for {sponsor_name}"
        banner_message += "."

    return {
        "is_impersonating_driver": is_driver_impersonated(),
        "impersonation_banner_message": banner_message,
        "impersonation_exit_endpoint": "driver.stop_impersonation",
        "impersonation_exit_label": "Return to Sponsor View",
    }


def get_driver_dashboard_data(driver: Driver, *, include_applications: bool) -> dict:
    active_sponsorship = get_active_sponsorship(driver)
    available_organizations = (
        get_available_organizations(driver.driver_id) if include_applications else []
    )
    transactions = []
    organization = None
    sponsor_rules = None
    point_value = None

    if active_sponsorship:
        organization = active_sponsorship.organization
        sponsor_rules = organization.rules if organization else None
        point_value = organization.point_value if organization else None
        transactions = (
            PointTransaction.query.filter_by(
                driver_id=driver.driver_id,
                organization_id=active_sponsorship.organization_id,
            )
            .order_by(PointTransaction.create_time.desc())
            .all()
        )

    notifications_query = Notification.query.filter_by(driver_id=driver.driver_id)

    if not driver.point_change_alert:
        notifications_query = notifications_query.filter(
            Notification.category != NotificationCategory.POINT_CHANGE
        )

    if not driver.order_alert:
        notifications_query = notifications_query.filter(
            Notification.category != NotificationCategory.ORDER_PLACED
        )

    notifications = notifications_query.order_by(Notification.create_time.desc()).all()
    orders = (
        Order.query.filter_by(driver_id=driver.driver_id)
        .order_by(Order.create_time.desc())
        .all()
    )

    return {
        "active_sponsorship": active_sponsorship,
        "available_organizations": available_organizations,
        "organization": organization,
        "transactions": transactions,
        "sponsor_rules": sponsor_rules,
        "point_value": point_value,
        "orders": orders,
        "notifications": notifications,
    }


def filter_driver_orders(driver_id: int, search: str, status: str) -> list[Order]:
    orders_query = Order.query.filter_by(driver_id=driver_id)

    if search:
        if search.isdigit():
            orders_query = orders_query.filter(Order.order_id == int(search))
        else:
            orders_query = orders_query.filter(db.false())

    if status:
        try:
            orders_query = orders_query.filter(Order.order_status == OrderStatus(status))
        except ValueError:
            orders_query = orders_query.filter(db.false())

    return orders_query.order_by(Order.create_time.desc()).all()


def update_driver_account(user: User, *, first_name: str, last_name: str, email: str) -> None:
    user.first_name = first_name.strip()
    user.last_name = last_name.strip()
    user.email = email.strip()
    db.session.commit()


def submit_driver_application(driver: Driver, organization_id: int, form_data: dict) -> None:
    existing = DriverApplication.query.filter_by(
        driver_id=driver.driver_id,
        organization_id=organization_id,
        status=DriverApplicationStatus.PENDING,
    ).first()

    if existing:
        raise ValueError("You already have a pending application with this sponsor.")

    application = DriverApplication(
        driver_id=driver.driver_id,
        organization_id=organization_id,
        status=DriverApplicationStatus.PENDING,
        full_name=form_data.get("full_name", "").strip() or None,
        phone_number=form_data.get("phone_number", "").strip() or None,
        address=form_data.get("address", "").strip() or None,
        experience=form_data.get("experience", "").strip() or None,
        reason=form_data.get("reason", "").strip() or None,
    )
    db.session.add(application)
    db.session.commit()


def redeem_catalog_item_for_driver(
    driver: Driver,
    *,
    acting_user_id: int,
    catalog_id: int,
) -> str:
    sponsorship = get_active_sponsorship(driver)
    if not sponsorship:
        raise ValueError("You must be affiliated with an active sponsor to redeem points.")

    item = SponsorCatalogItem.query.filter_by(
        catalog_id=catalog_id,
        organization_id=sponsorship.organization_id,
    ).first()
    if not item:
        raise LookupError("Product not found in your sponsor's catalog.")

    cost = item.points_required
    if sponsorship.point_balance < cost:
        raise RuntimeError(
            f"Insufficient points. You need {cost} points but have {sponsorship.point_balance}."
        )

    sponsorship.point_balance -= cost

    order = Order(
        driver_id=driver.driver_id,
        organization_id=sponsorship.organization_id,
        placed_by_user_id=acting_user_id,
        points=cost,
        order_status=OrderStatus.PENDING,
    )
    db.session.add(order)
    db.session.flush()

    db.session.add(
        OrderItem(
            order_id=order.order_id,
            catalog_id=item.catalog_id,
            quantity=1,
            price=cost,
        )
    )
    db.session.add(
        Notification(
            driver_id=driver.driver_id,
            issued_by_user_id=acting_user_id,
            category=NotificationCategory.ORDER_PLACED,
            message=(
                f"Order placed: {item.product_name} for {cost} points. "
                f"Order #{order.order_id} is now pending."
            ),
        )
    )

    db.session.commit()
    return f"Successfully redeemed {item.product_name} for {cost} points!"


def toggle_driver_alert(driver: Driver, alert_type: str) -> str:
    if alert_type == "order":
        driver.order_alert = not driver.order_alert
        state = "enabled" if driver.order_alert else "disabled"
        message = f"Order placement alerts {state}."
    else:
        driver.point_change_alert = not driver.point_change_alert
        state = "enabled" if driver.point_change_alert else "disabled"
        message = f"Point change alerts {state}."

    db.session.commit()
    return message


def cancel_driver_order(driver: Driver, order_id: int) -> str:
    order = next((o for o in driver.orders if o.order_id == order_id), None)
    if not order:
        raise LookupError("Order not found.")
    if order.order_status == OrderStatus.CANCELLED:
        raise ValueError("Order is already cancelled.")
    if order.order_status == OrderStatus.COMPLETED:
        raise ValueError("Completed orders cannot be cancelled.")

    sponsorship = get_active_sponsorship(driver)
    if sponsorship and sponsorship.organization_id == order.organization_id:
        sponsorship.point_balance += order.points

    order.order_status = OrderStatus.CANCELLED
    db.session.commit()
    return "Order cancelled and points refunded."


def get_sponsor_user_for_impersonation_return(sponsor_user_id: int) -> User | None:
    sponsor_user = User.query.get(sponsor_user_id)
    if not sponsor_user or sponsor_user.role_type != RoleType.SPONSOR:
        return None
    return sponsor_user
