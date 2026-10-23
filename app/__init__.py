import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf import CSRFProtect

from config import Config

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)  # batch = alterações seguras no SQLite
    csrf.init_app(app)

    from app import models  # noqa: F401  (registra os modelos)
    from app.routes import bp
    app.register_blueprint(bp)

    from app.utils import formatar_data, formatar_moeda
    app.jinja_env.filters["data_br"] = formatar_data
    app.jinja_env.filters["moeda"] = formatar_moeda

    from app.seed import registrar_comandos
    registrar_comandos(app)

    from app.alertas import registrar_comando_alertas
    registrar_comando_alertas(app)

    return app