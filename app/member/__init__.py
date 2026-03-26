from flask import Blueprint

member = Blueprint("member", __name__)

from app.member import routes  # noqa: F401, E402
