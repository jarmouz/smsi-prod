"""Contrôle d'accès par rôle pour le SMSI.
- RSSI : accès complet (administration comprise)
- Contributeur : création/édition des objets opérationnels
- Auditeur : gère les audits et constats
- Lecteur : lecture seule
"""
from functools import wraps

from flask import abort
from flask_login import current_user
from app.models import Role


def rssi_required(fn):
    @wraps(fn)
    def w(*a, **k):
        if not current_user.is_authenticated or current_user.role != Role.RSSI:
            abort(403)
        return fn(*a, **k)
    return w


def editor_required(fn):
    """RSSI ou Contributeur (édition des objets opérationnels)."""
    @wraps(fn)
    def w(*a, **k):
        if not current_user.is_authenticated or current_user.role not in (Role.RSSI, Role.CONTRIBUTEUR):
            abort(403)
        return fn(*a, **k)
    return w


def auditor_required(fn):
    """RSSI ou Auditeur (gestion des audits)."""
    @wraps(fn)
    def w(*a, **k):
        if not current_user.is_authenticated or current_user.role not in (Role.RSSI, Role.AUDITEUR):
            abort(403)
        return fn(*a, **k)
    return w
