from flask import Flask, render_template
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFError, CSRFProtect

from config import Config, DEV_SECRET_KEY

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'
csrf = CSRFProtect()


def create_app(overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)      # the tests pass their own database here

    if app.config['APP_ENV'] == 'production' and app.config['SECRET_KEY'] == DEV_SECRET_KEY:
        raise RuntimeError('Set the SECRET_KEY environment variable before running in production.')

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)      # rejects any POST that does not carry a valid CSRF token

    from app.routes.auth    import auth_bp
    from app.routes.main    import main_bp
    from app.routes.booking import booking_bp
    from app.routes.admin   import admin_bp

    app.register_blueprint(auth_bp,    url_prefix='/auth')
    app.register_blueprint(main_bp,    url_prefix='/')
    app.register_blueprint(booking_bp, url_prefix='/booking')
    app.register_blueprint(admin_bp,   url_prefix='/admin')

    @app.context_processor
    def inject_globals():
        from app.clock import local_now
        return {'now': local_now()}

    @app.errorhandler(CSRFError)
    def csrf_failed(error):
        return render_template(
            'error.html', code=400, title='Request not accepted',
            message='This form has expired or did not come from this site. Go back, reload the page and try again.',
        ), 400

    @app.errorhandler(404)
    def not_found(error):
        return render_template(
            'error.html', code=404, title='Page not found',
            message='The page you are looking for does not exist.',
        ), 404

    return app
