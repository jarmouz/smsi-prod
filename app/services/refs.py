from datetime import datetime

from app.extensions import db


def next_ref(model, prefix, width=4, yearly=True):
    year = datetime.utcnow().year
    if yearly:
        like = f"{prefix}-{year}-%"
        count = db.session.query(model).filter(model.ref.like(like)).count()
        return f"{prefix}-{year}-{count + 1:0{width}d}"
    count = db.session.query(model).count()
    return f"{prefix}-{count + 1:0{width}d}"
