import os

from dotenv import load_dotenv
from sqlalchemy.engine import URL

load_dotenv()

# Only used when SECRET_KEY is not set. The app refuses to start with it in production.
DEV_SECRET_KEY = 'dev-secret-key-change-in-production'


def database_uri():
    """Build the database URL.

    Hosting platforms usually give one DATABASE_URL. For a local MySQL the
    separate DB_* settings from .env are used instead.
    """
    url = os.environ.get('DATABASE_URL')
    if url:
        # platforms hand out "mysql://...", SQLAlchemy also needs the driver name
        if url.startswith('mysql://'):
            url = 'mysql+pymysql://' + url[len('mysql://'):]
        return url

    return URL.create(
        'mysql+pymysql',
        username=os.environ.get('DB_USER', 'root'),
        password=os.environ.get('DB_PASSWORD', ''),
        host=os.environ.get('DB_HOST', 'localhost'),
        port=int(os.environ.get('DB_PORT', '3306')),
        database=os.environ.get('DB_NAME', 'subway_system'),
    ).render_as_string(hide_password=False)


class Config:
    # "development" or "production"
    APP_ENV = os.environ.get('APP_ENV', 'development')

    SECRET_KEY = os.environ.get('SECRET_KEY') or DEV_SECRET_KEY

    SQLALCHEMY_DATABASE_URI = database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # hosted MySQL servers close idle connections, so test a connection before using it
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True, 'pool_recycle': 280}

    # every POST form must carry a CSRF token (see app/__init__.py)
    WTF_CSRF_ENABLED = True

    # cookies: not readable from JavaScript, not sent on cross-site POSTs,
    # and HTTPS-only in production
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = APP_ENV == 'production'
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE = APP_ENV == 'production'

    # all train times are Chennai local time, whatever clock the server uses
    APP_TIMEZONE = os.environ.get('APP_TIMEZONE', 'Asia/Kolkata')

    # demo data (2 lines, 8 stations, 60 days of schedules, demo accounts)
    SEED_DEMO_DATA = os.environ.get('SEED_DEMO_DATA', '1' if APP_ENV != 'production' else '0') == '1'
