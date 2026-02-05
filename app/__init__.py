from flask import Flask

from app.auth import auth_bp

def create_app():
    app = Flask(__name__)

    # config setup

    # extensions init

    # blueprint registration
    app.register_blueprint(auth_bp)
    
    return app
