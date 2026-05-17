from __future__ import annotations

from flask_login import current_user, login_required
from flask import render_template

from ..models import CreditHold, CreditLedger
from . import credits_bp


@credits_bp.route("/ledger")
@login_required
def ledger():
    entries = current_user.credit_entries.order_by(CreditLedger.created_at.desc()).all()
    holds = current_user.credit_holds.filter(CreditHold.status == "reserved").all()
    return render_template("credits/ledger.html", entries=entries, holds=holds)
