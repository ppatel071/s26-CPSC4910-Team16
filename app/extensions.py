# This file is for creating shared objects in one place so they can be safely imported across the app 
# without circular imports while still supporting the app factory pattern.
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
  pass

db = SQLAlchemy(model_class=Base)