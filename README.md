# s26-CPSC4910-Team16

### Dev Setup:
1. (optional) Create a python venv and activate it
2. `pip install -r requirements.txt`
3. `cp .env.template .env` Copies the template to create a .env file, fill in .env with the right info
4. `python run.py`

Check teams for the DB_URI in our channel

### Structure:
- run.py is the app entry point
- create_app() in app/__init__.py builds and configures the Flask app
- Blueprints define routes in feature-based modules (auth, driver, reports, etc)
- Blueprints are registered in create_app(), which connects all routes to the app
- The database is accessed through SQLAlchemy and models are in app/models