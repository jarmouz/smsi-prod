"""Géométrie des graphiques d'indicateurs (SVG rendu côté serveur, sans JavaScript)."""


def _nice_ticks(lo, hi, n=4):
    import math
    span = hi - lo or abs(hi) or 1
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    start = math.floor(lo / step) * step
    ticks, t = [], start
    while t <= hi + step * 0.001:
        ticks.append(round(t, 10))
        t += step
    return ticks


def kpi_chart(ind, width=640, height=220, last_n=24):
    """Points chronologiques, ligne de cible / d'alerte et graduations pour un indicateur."""
    pts = list(reversed(ind.measurements[:last_n]))
    left, right, top, bottom = (44, 56, 14, 26) if height > 80 else (2, 2, 4, 4)
    values = [m.value for m in pts] + [ind.target] + ([ind.alert] if ind.alert is not None else [])
    lo, hi = min(values), max(values)
    pad = (hi - lo) * 0.12 or abs(hi) * 0.1 or 1
    lo, hi = lo - pad, hi + pad
    if min(values) >= 0 and lo < 0:
        lo = 0
    ticks = _nice_ticks(lo, hi) if height > 80 else []
    if ticks:
        lo, hi = min(lo, ticks[0]), max(hi, ticks[-1])
    w, h = width - left - right, height - top - bottom
    y = lambda v: round(top + h - (v - lo) / (hi - lo) * h, 1)  # noqa: E731
    n = len(pts)
    x = lambda k: round(left + (w * k / (n - 1) if n > 1 else w / 2), 1)  # noqa: E731
    points = [{"x": x(k), "y": y(m.value), "value": ind.fmt(m.value), "period": m.period.strftime("%d/%m/%Y"),
               "short": m.period.strftime("%m/%y"), "state": ind.evaluate(m.value)} for k, m in enumerate(pts)]
    return {
        "width": width, "height": height, "left": left, "right": width - right, "top": top, "bottom": top + h,
        "points": points, "path": " ".join(f"{p['x']},{p['y']}" for p in points),
        "target_y": y(ind.target), "alert_y": y(ind.alert) if ind.alert is not None else None,
        "ticks": [{"y": y(t), "label": ind.fmt(t)} for t in ticks],
        "xlabels": [p for k, p in enumerate(points) if n <= 8 or k % max(1, n // 6) == 0 or k == n - 1],
    }


def init_app(app):
    @app.context_processor
    def _inject():
        return {"kpi_chart": kpi_chart}
