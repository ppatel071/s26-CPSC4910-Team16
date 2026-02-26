from dotenv import load_dotenv
load_dotenv()

import os
from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    debug = os.getenv('DEBUG', 'false').lower() == 'true'
    app.run(debug=debug)