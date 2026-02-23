import datetime as dt
from sqlalchemy import func
from app.extensions import db
from app.models import SponsorOrganization, User, Order
from app.sponsor.services import update_sponsor_organization


def get_all_sponsors():
    return SponsorOrganization.query.order_by(SponsorOrganization.name.asc()).all()


def get_sponsor_by_id(organization_id: int) -> SponsorOrganization:
    org = SponsorOrganization.query.get(organization_id)
    if org is None:
        raise ValueError('No organization exists for that id')
    return org


def admin_update_sponsor(organization_id: int, name: str) -> SponsorOrganization:
    org = get_sponsor_by_id(organization_id)
    return update_sponsor_organization(org, name, str(org.point_value))


def get_sales_by_sponsor(detail: bool):
    if detail:
        return (
            db.session.query(
                SponsorOrganization.name.label('sponsor_name'),
                Order.points.label('amount'),
                Order.create_time.label('sale_time'),
                User.username.label('driver_username'),
            )
            .join(Order.organization)
            .join(Order.placed_by_user)
            .order_by(SponsorOrganization.name.asc(), Order.create_time.desc())
            .all()
        )

    return (
        db.session.query(
            SponsorOrganization.name.label('sponsor_name'),
            func.count(Order.order_id).label('sale_count'),
            func.sum(Order.points).label('total_amount'),
        )
        .join(Order.organization)
        .group_by(SponsorOrganization.name)
        .order_by(SponsorOrganization.name.asc())
        .all()
    )


def get_sales_by_driver(detail: bool):
    if detail:
        return (
            db.session.query(
                User.username.label('driver_username'),
                Order.points.label('amount'),
                Order.create_time.label('sale_time'),
                SponsorOrganization.name.label('sponsor_name'),
            )
            .join(Order.placed_by_user)
            .join(Order.organization)
            .order_by(User.username.asc(), Order.create_time.desc())
            .all()
        )

    return (
        db.session.query(
            User.username.label('driver_username'),
            func.count(Order.order_id).label('sale_count'),
            func.sum(Order.points).label('total_amount'),
        )
        .join(Order.placed_by_user)
        .group_by(User.username)
        .order_by(User.username.asc())
        .all()
    )


def get_driver_purchase_summary(start_date: dt.date, end_date: dt.date):
    start_dt = dt.datetime.combine(start_date, dt.time.min)
    end_dt = dt.datetime.combine(end_date + dt.timedelta(days=1), dt.time.min)

    return (
        db.session.query(
            User.username.label('driver_username'),
            func.count(Order.order_id).label('purchase_count'),
            func.sum(Order.points).label('total_amount'),
        )
        .join(Order.placed_by_user)
        .filter(Order.create_time >= start_dt, Order.create_time < end_dt)
        .group_by(User.username)
        .order_by(User.username.asc())
        .all()
    )
