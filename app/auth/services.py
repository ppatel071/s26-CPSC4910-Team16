# Business logic for the auth routes
import datetime as dt
import re
from app.models import User, RoleType, Driver, PasswordChange, PasswordChangeType, LoginAttempt
from app.extensions import db
from werkzeug.security import check_password_hash, generate_password_hash
from typing import Tuple
from redmail import gmail

MAX_FAILED_LOGIN_ATTEMPTS = 5


def build_lockout_message() -> str:
    return (
        f'Your account has been locked after {MAX_FAILED_LOGIN_ATTEMPTS} failed login attempts. '
        'Please contact an admin to unlock it.'
    )


def _record_login_attempt(user: User | None, username: str, success: bool) -> None:
    db.session.add(
        LoginAttempt(
            user_id=user.user_id if user else None,
            username_attempted=username,
            success=success,
        )
    )


def validate_complexity(password: str, confpass: str | None = None) -> Tuple[bool, str]:
    if len(password) < 8:
        return False, 'Password must be at least 8 characters'
    if not re.search(r'[A-Z]', password):
        return False, 'Password must have a capital letter'
    if not re.search(r'[a-z]', password):
        return False, 'Password must have a lowercase letter'
    if not re.search(r'\d', password):
        return False, 'Password must have a number'
    if confpass is not None and password != confpass:
        return False, 'Passwords do not match'

    return True, ''


def check_unique(username: str, email: str) -> Tuple[bool, str]:
    user = User.query.filter_by(username=username).first()
    if user:
        return False, 'Username is taken'

    email_check = User.query.filter_by(email=email).first()
    if email_check:
        return False, 'An account exists belonging to this email'

    return True, ''


def authenticate(username: str, password: str) -> Tuple[User | None, str]:
    clean_username = (username or '').strip()
    user = User.query.filter_by(username=clean_username).first()
    if not user:
        _record_login_attempt(None, clean_username, False)
        db.session.commit()
        return None, 'Invalid username or password'
    if not user.is_user_active:
        _record_login_attempt(user, clean_username, False)
        db.session.commit()
        return None, 'Your account has been deactivated. Please contact an admin.'
    if user.is_login_locked:
        _record_login_attempt(user, clean_username, False)
        db.session.commit()
        return None, build_lockout_message()
    if check_password_hash(user.password, password):
        user.failed_login_attempts = 0
        _record_login_attempt(user, clean_username, True)
        db.session.commit()
        return user, ''

    user.failed_login_attempts += 1
    error = 'Invalid username or password'

    if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
        user.is_login_locked = True
        user.locked_at = dt.datetime.now(tz=dt.timezone.utc)
        error = build_lockout_message()

    _record_login_attempt(user, clean_username, False)
    db.session.commit()
    return None, error


def register_user(
    username: str,
    password: str,
    role: RoleType,
    email: str,
    first_name: str,
    last_name: str,
    confpass: str | None = None,
    *,
    commit: bool = True,
) -> User:
    valid, msg = validate_complexity(password, confpass)
    if not valid:
        raise ValueError(msg)

    valid, msg = check_unique(username, email)
    if not valid:
        raise ValueError(msg)

    if not username:
        raise ValueError('Username is required')
    if not password:
        raise ValueError('Password is required')
    if not email:
        raise ValueError('Email is required')

    password_hash = generate_password_hash(password)

    user = User(
        username=username,
        password=password_hash,
        role_type=role,
        email=email,
        first_name=first_name,
        last_name=last_name
    )

    db.session.add(user)
    if commit:
        db.session.commit()
    else:
        db.session.flush()

    if role == RoleType.DRIVER:
        driver = Driver(
            user_id=user.user_id,
        )

        db.session.add(driver)
        if commit:
            db.session.commit()
        else:
            db.session.flush()
    return user


def send_reset_email(user_email: str) -> int:
    user_info = (
        db.session.query(
            User.user_id,
            User.email
        )
        .filter((User.username == user_email) | (User.email == user_email))
        .first()
    )

    email = user_info.email
    user_id = user_info.user_id

    if not email:
        raise ValueError('Email not found')
    
    ## send email

    return user_id

def hash_id(user_id : int) -> str:
    return generate_password_hash(str(user_id))[17:]
def check_id_hash(user_id : int, id_hash : str) -> bool:
    return check_password_hash("scrypt:32768:8:1$" + id_hash, str(user_id))
    
def email_reset_password(user: User, new_password: str):
    valid, msg = validate_complexity(new_password)
    if not valid:
        raise ValueError(msg)
    
    user.password = generate_password_hash(new_password)

    password_change = PasswordChange(
        user_id = user.user_id,
        change_type=PasswordChangeType.RESET
    )

    db.session.add(password_change)
    db.session.commit()

def reset_user_password(user: User, current_password: str, new_password: str):
    if not check_password_hash(user.password, current_password):
        raise ValueError('Current password is incorrect')

    valid, msg = validate_complexity(new_password)
    if not valid:
        raise ValueError(msg)

    user.password = generate_password_hash(new_password)

    password_change = PasswordChange(
        user_id=user.user_id,
        change_type=PasswordChangeType.UPDATE
    )

    db.session.add(password_change)
    db.session.commit()
