from dotenv import load_dotenv
load_dotenv()

import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    debug = os.getenv('DEBUG', 'false').lower() == 'true'
    app.run(debug=debug)
