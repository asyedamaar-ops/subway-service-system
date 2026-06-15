from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    from app.routes.auth    import auth_bp
    from app.routes.main    import main_bp
    from app.routes.booking import booking_bp
    from app.routes.admin   import admin_bp

    app.register_blueprint(auth_bp,    url_prefix='/auth')
    app.register_blueprint(main_bp,    url_prefix='/')
    app.register_blueprint(booking_bp, url_prefix='/booking')
    app.register_blueprint(admin_bp,   url_prefix='/admin')

    return app
