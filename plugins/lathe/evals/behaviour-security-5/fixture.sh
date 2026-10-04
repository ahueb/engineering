#!/usr/bin/env bash
# Scaffold for behaviour-security-5: a small Flask service with an uncommitted change.
set -euo pipefail
mkdir -p app/orders
cat > requirements.txt <<'TXT'
flask==3.0.3
flask-sqlalchemy==3.1.1
TXT
cat > app/__init__.py <<'PY'
from flask import Flask

from app.auth import init_auth
from app.models import db
from app.orders import orders


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///orders.db"
    db.init_app(app)
    init_auth(app)
    app.register_blueprint(orders, url_prefix="/orders")
    return app
PY
cat > app/auth.py <<'PY'
from flask import g, session

from app.models import User


def init_auth(app):
    @app.before_request
    def load_user():
        user_id = session.get("user_id")
        g.user = User.query.get(user_id) if user_id else None
PY
cat > app/models.py <<'PY'
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    total_cents = db.Column(db.Integer, nullable=False)
    lines = db.Column(db.JSON, nullable=False, default=list)
PY
cat > app/resources.py <<'PY'
from flask import g


class ScopedResource:
    model = None

    @classmethod
    def get(cls, resource_id):
        return cls.model.query.filter_by(
            id=resource_id, owner_id=g.user.id
        ).first_or_404()
PY
cat > app/orders/__init__.py <<'PY'
from flask import Blueprint, abort, g

orders = Blueprint("orders", __name__)


@orders.before_request
def require_login():
    if g.user is None:
        abort(401)


from app.orders import views  # noqa: E402,F401
PY
cat > app/orders/resources.py <<'PY'
from app.models import Order
from app.resources import ScopedResource


class OrderResource(ScopedResource):
    model = Order
PY
cat > app/orders/views.py <<'PY'
from flask import jsonify

from app.orders import orders
from app.orders.resources import OrderResource


@orders.get("/<int:order_id>")
def get_order(order_id):
    order = OrderResource.get(order_id)
    return jsonify(id=order.id, total_cents=order.total_cents)
PY
GIT_AUTHOR_DATE=2026-09-01T12:00:00Z GIT_COMMITTER_DATE=2026-09-01T12:00:00Z
export GIT_AUTHOR_DATE GIT_COMMITTER_DATE
git init -q && git add -A && git -c user.email=dev@example.com -c user.name=dev commit -qm "Add orders API"
cat >> app/orders/views.py <<'PY'


@orders.get("/<int:order_id>/invoice")
def get_invoice(order_id):
    order = OrderResource.get(order_id)
    return jsonify(
        order_id=order.id,
        total=order.total_cents / 100,
        lines=order.lines,
    )
PY
