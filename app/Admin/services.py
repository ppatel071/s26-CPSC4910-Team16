import datetime as dt
from sqlalchemy import func
from app.extensions import db
from app.models import SponsorOrganization, User
from app.sponsor.services import update_sponsor_organization
from app.models.sales import Sale

def get_all_sponsors():
    return SponsorOrganization.query.order_by(SponsorOrganization.name.asc()).all()

def get_sponsor_by_id(organization_id: int) -> SponsorOrganization | None:
    return SponsorOrganization.query.get(organization_id)

def admin_update_sponsor(organization_id: int, name: str, point_value: str) -> SponsorOrganization:
    org = get_sponsor_by_id(organization_id)
    return update_sponsor_organization(org, name, point_value)


def get_sales_by_sponsor(detail: bool):
    if detail:
        return (
            db.session.query(
                SponsorOrganization.name.label('sponsor_name'),
                Sale.amount.label('amount'),
                Sale.sale_time.label('sale_time'),
                User.username.label('driver_username'),
            )
            .join(Sale, Sale.sponsor_id == SponsorOrganization.organization_id)
            .join(User, User.user_id == Sale.driver_user_id)
            .order_by(SponsorOrganization.name.asc(), Sale.sale_time.desc())
            .all()
        )

    return (
        db.session.query(
            SponsorOrganization.name.label('sponsor_name'),
            func.count(Sale.sale_id).label('sale_count'),
            func.sum(Sale.amount).label('total_amount'),
        )
        .join(Sale, Sale.sponsor_id == SponsorOrganization.organization_id)
        .group_by(SponsorOrganization.name)
        .order_by(SponsorOrganization.name.asc())
        .all()
    )


def get_sales_by_driver(detail: bool):
    if detail:
        return (
            db.session.query(
                User.username.label('driver_username'),
                Sale.amount.label('amount'),
                Sale.sale_time.label('sale_time'),
                SponsorOrganization.name.label('sponsor_name'),
            )
            .join(Sale, Sale.driver_user_id == User.user_id)
            .join(SponsorOrganization, SponsorOrganization.organization_id == Sale.sponsor_id)
            .order_by(User.username.asc(), Sale.sale_time.desc())
            .all()
        )

    return (
        db.session.query(
            User.username.label('driver_username'),
            func.count(Sale.sale_id).label('sale_count'),
            func.sum(Sale.amount).label('total_amount'),
        )
        .join(Sale, Sale.driver_user_id == User.user_id)
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
            func.count(Sale.sale_id).label('purchase_count'),
            func.sum(Sale.amount).label('total_amount'),
        )
        .join(Sale, Sale.driver_user_id == User.user_id)
        .filter(Sale.sale_time >= start_dt, Sale.sale_time < end_dt)
        .group_by(User.username)
        .order_by(User.username.asc())
        .all()
    )

