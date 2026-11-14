"""Entry point.

Local development:   python run.py
Production (Procfile): gunicorn run:app
"""
import os

from app import create_app
from app.seed import init_database

app = create_app()
init_database(app)      # creates missing tables, seeds demo data when SEED_DEMO_DATA=1


if __name__ == '__main__':
    app.run(debug=False, host=os.environ.get('HOST', '127.0.0.1'), port=int(os.environ.get('PORT', 5000)))
