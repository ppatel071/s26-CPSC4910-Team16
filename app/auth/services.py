# Business logic for the auth routes
from app.models.users import User, RoleType
from app.extensions import db
from werkzeug.security import check_password_hash, generate_password_hash


def login_user(username: str, password: str) -> bool:
    user = User.query.filter_by(username=username).first()
    if not user:
        return False
    return check_password_hash(user.password, password)


def register_user(username: str, password: str, role: str, email: str):
    role = role.upper()
    password_hash = generate_password_hash(password)
    user = User(
        username=username,
        password=password_hash,
        role_type=RoleType[role],
        email=email,
    )
    db.session.add(user)
    db.session.commit()
