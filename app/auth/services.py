# Business logic for the auth routes
import re
from app.models import User, RoleType
from app.extensions import db
from werkzeug.security import check_password_hash, generate_password_hash
from typing import Tuple

def validate_complexity(password: str) -> Tuple[bool, str]:
    if len(password) < 8:
        return False, 'Password must be at least 8 characters'
    if not re.search(r'[A-Z]', password):
        return False, 'Password must have a capital letter'
    if not re.search(r'[a-z]', password):
        return False, 'Password must have a lowercase letter'
    if not re.search(r'\d', password):
        return False, 'Password must have a number'
    return True, ''

def authenticate(username: str, password: str) -> User | None:
    user = User.query.filter_by(username=username).first()
    if not user:
        return None
    if check_password_hash(user.password, password):
        return user
    return None


def register_user(username: str, password: str, role: str, email: str):
    valid, msg = validate_complexity(password)
    if not valid:
        raise ValueError(msg)
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


def reset_user_password(
    user,
    current_password: str,
    new_password: str,
):
    if not check_password_hash(user.password, current_password):
        raise ValueError('Current password is incorrect')

    valid, msg = validate_complexity(new_password)
    if not valid:
        raise ValueError(msg)

    user.password = generate_password_hash(new_password)
    db.session.commit()
