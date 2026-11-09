"""Time handling (spec 0.2, I-5, I-6): local wall-clock times, `Window` for uncertain launch times, solar-hour limits.

    Window("2027-06-16 10:00")                                         one time
    Window("2027-06-16 09:00-13:00")                                   a day plus start and end: uniform
    Window(("2027-06-16 09:00", "2027-06-18 15:00"))                   two date-times: uniform
    Window(("2027-06-16 10:00", "2027-06-16 08:00", "2027-06-17 16:00"))   three: most likely, earliest, latest: triangular
    Window("2027-06-16 10:00", earliest="08:00", latest="2027-06-17 16:00")   same, keyword form (bare clock times take the date of the first)
    Window(earliest="2027-06-16 08:00", latest="2027-06-16 13:00")     uniform
    Window([("2027-06-16 08:00", "2027-06-16 11:00"), ("2027-06-18", "2027-06-19")], weights=None, exclude=["12:00-14:00"])

A naive time is the LOCAL WALL-CLOCK time at the site (zone from sites.toml or `tz=`); solar time is derived (mean solar time = UTC + lon / 15 h) and only draws inside 06-21 h solar are
kept; the share that was cut is reported. `resolve(...)` turns a Window into a discrete distribution (5-minute cells) over UTC instants; `sample(n, rng)` draws from it.
Only stdlib + numpy; zoneinfo needs the `tzdata` package on Windows (a clear error says so).
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

import numpy as np

__all__ = ["Window", "ResolvedWindow", "WindowError", "get_zone", "solar_hour", "parse_moment", "describe_local"]

STEP_MIN = 5
SOLAR_LO, SOLAR_HI = 6.0, 21.0


class WindowError(ValueError):
    """A time specification that cannot be used (the message says what to change)."""


def get_zone(name):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception as e:   # noqa: BLE001  (ZoneInfoNotFoundError, or no tzdata)
        raise WindowError(f"time zone {name!r} is not available ({e}). On Windows run: pip install tzdata") from e


def solar_hour(utc, lon):
    """Mean solar hour (0-24) at longitude `lon` for naive-UTC datetimes or a datetime64 array."""
    if isinstance(utc, np.ndarray):
        sec = (utc - utc.astype("datetime64[D]")) / np.timedelta64(1, "s")
        return (sec / 3600.0 + lon / 15.0) % 24.0
    return (utc.hour + utc.minute / 60.0 + utc.second / 3600.0 + lon / 15.0) % 24.0


_CLOCK = re.compile(r"^\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*$", re.I)


def _clock(text):
    """'09:00', '9am', '14:30', '10:15pm' -> minutes after midnight, or None."""
    m = _CLOCK.match(text)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").lower()
    if ap == "pm" and h < 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    if not (0 <= h <= 24 and 0 <= mi < 60) or (h == 24 and mi):
        return None
    return h * 60 + mi


def parse_moment(x, tz, ref=None, now=None):
    """-> (aware datetime in tz, date_only: bool). Accepts datetime, ISO date or date-time, bare clock ('08:00', '10am', takes the date of `ref`), 'today 14:00', 'tomorrow 10am'."""
    now = now or datetime.now(tz)
    if isinstance(x, datetime):
        return (x if x.tzinfo else x.replace(tzinfo=tz)), False
    if isinstance(x, date):
        return datetime.combine(x, time(0), tz), True
    s = str(x).strip()
    low = s.lower()
    base = None
    for word, delta in (("today", 0), ("tomorrow", 1)):
        if low.startswith(word):
            base, s = (now.astimezone(tz).date() + timedelta(days=delta)), s[len(word):].strip()
            break
    if base is not None:
        mins = 0 if not s else _clock(s)
        if mins is None:
            raise WindowError(f"cannot read the time of day in {x!r} (try '14:00' or '10am')")
        return datetime.combine(base, time(0), tz) + timedelta(minutes=mins), not s
    mins = _clock(s)
    if mins is not None:
        if ref is None:
            raise WindowError(f"{x!r} is only a clock time: give the date too (e.g. '2027-06-16 {s}')")
        return datetime.combine(ref.date(), time(0), tz) + timedelta(minutes=mins), False
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            return datetime.combine(date.fromisoformat(s), time(0), tz), True
        t = datetime.fromisoformat(s.replace(" ", "T", 1))
    except ValueError as e:
        raise WindowError(f"cannot read the time {x!r}: use '2027-06-16 09:00', '2027-06-16', '09:00', 'today 14:00' or 'tomorrow 10am'") from e
    return (t if t.tzinfo else t.replace(tzinfo=tz)), False


def describe_local(utc, tz):
    t = utc.replace(tzinfo=timezone.utc).astimezone(tz)
    return t.strftime("%Y-%m-%d %H:%M %Z")


@dataclass(frozen=True)
class _Part:
    start: datetime          # aware, local
    end: datetime
    mode: datetime = None    # triangular peak, or None for uniform
    weight: float = None


@dataclass(frozen=True)
class ResolvedWindow:
    """A launch-time distribution on 5-minute cells (UTC)."""
    cells_utc: np.ndarray            # datetime64[m], cell starts
    prob: np.ndarray                 # sums to 1
    cut_share: float                 # share of the requested probability removed (night hours, exclusions)
    kind: str
    description: str
    day_share: dict = field(default_factory=dict)

    def sample(self, n, rng=None):
        """n instants (datetime64[s], UTC), uniform inside the chosen cell."""
        rng = rng or np.random.default_rng(0)
        idx = rng.choice(len(self.cells_utc), size=n, p=self.prob)
        return self.cells_utc[idx].astype("datetime64[s]") + (rng.random(n) * STEP_MIN * 60).astype("timedelta64[s]")

    @property
    def single(self):
        return len(self.cells_utc) == 1 and self.kind == "single"


class Window:
    """Launch-time specification (immutable). See the module docstring for every accepted form."""

    def __init__(self, spec=None, *, earliest=None, latest=None, exclude=(), weights=None, tz=None):
        self._spec, self._earliest, self._latest = spec, earliest, latest
        self.exclude = tuple(exclude)
        self.weights = None if weights is None else tuple(weights)
        self.tz_name = tz
        if spec is None and (earliest is None or latest is None):
            raise WindowError("give a time, or both earliest= and latest=")

    # -- normalise the spec into parts
    def _parts(self, tz, now):
        spec = self._spec
        mk = lambda x, ref=None: parse_moment(x, tz, ref, now)
        parts = []
        if spec is None:                                                             # Window(earliest=, latest=)
            a, _ = mk(self._earliest)
            b, _ = mk(self._latest, a)
            parts.append(_Part(a, b))
        elif self._earliest is not None or self._latest is not None:                 # Window("most likely", earliest=, latest=)
            m, _ = mk(spec)
            a, _ = mk(self._earliest, m) if self._earliest is not None else (m, False)
            b, _ = mk(self._latest, m) if self._latest is not None else (m, False)
            parts.append(_Part(a, b, m))
        else:
            for item in (spec if isinstance(spec, list) else [spec]):
                parts.append(self._one(item, mk))
        if self.weights is not None and len(self.weights) != len(parts):
            raise WindowError(f"weights has {len(self.weights)} values for {len(parts)} ranges")
        if self.weights is not None:
            parts = [_Part(p.start, p.end, p.mode, w) for p, w in zip(parts, self.weights)]
        return parts

    @staticmethod
    def _one(item, mk):
        if isinstance(item, (tuple, list)):
            if len(item) == 2:
                a, _ = mk(item[0])
                b, db = mk(item[1], a)
                return _Part(a, b + timedelta(days=1) if db else b)
            if len(item) == 3:
                m, _ = mk(item[0])
                a, _ = mk(item[1], m)
                b, _ = mk(item[2], m)
                if not (a <= m <= b):
                    raise WindowError(f"the most likely time {item[0]!r} must lie between the earliest {item[1]!r} and the latest {item[2]!r}")
                return _Part(a, b, m)
            raise WindowError("a time range has 2 values (earliest, latest) or 3 (most likely, earliest, latest)")
        if isinstance(item, str):
            m = re.fullmatch(r"\s*(.+?)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*-\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*", item, re.I)
            if m and _clock(m.group(2)) is not None and _clock(m.group(3)) is not None:      # "2027-06-16 09:00-13:00"
                a, _ = mk(f"{m.group(1)} {m.group(2)}")
                b, _ = mk(m.group(3), a)
                return _Part(a, b)
        t, date_only = mk(item)
        return _Part(t, t + timedelta(days=1)) if date_only else _Part(t, t, None, None)

    # -- resolve
    def resolve(self, lon, tz=None, now=None, solar=(SOLAR_LO, SOLAR_HI)):
        """-> ResolvedWindow for a site at longitude `lon` (zone `tz` or the window's own)."""
        tzo = tz if (tz is not None and not isinstance(tz, str)) else get_zone(tz or self.tz_name or "UTC")
        parts = self._parts(tzo, now)
        step = timedelta(minutes=STEP_MIN)
        cells, mass = [], []
        requested = 0.0
        for p in parts:
            a, b = p.start.astimezone(timezone.utc).replace(tzinfo=None), p.end.astimezone(timezone.utc).replace(tzinfo=None)
            if b < a:
                raise WindowError("the latest time is before the earliest")
            if a == b:                                                                    # a single instant
                cells.append(np.datetime64(a, "m"))
                mass.append(1.0 if p.weight is None else p.weight)
                requested += mass[-1]
                continue
            t0 = np.datetime64(a, "m")
            n = max(int(np.ceil((b - a) / step)), 1)
            c = t0 + np.arange(n) * np.timedelta64(STEP_MIN, "m")
            mid = (c - t0) / np.timedelta64(1, "m") + STEP_MIN / 2.0
            L = (b - a).total_seconds() / 60.0
            if p.mode is None:
                w = np.ones(n)
            else:                                                                         # triangular density with the peak at the most likely time
                m = min(max((p.mode.astimezone(timezone.utc).replace(tzinfo=None) - a).total_seconds() / 60.0, 0.0), L)
                left = mid / m if m > 0 else np.zeros(n)
                right = (L - mid) / (L - m) if L > m else np.zeros(n)
                w = np.maximum(np.where(mid <= m, left, right), 1e-6)
            w = w / w.sum() * (L if p.weight is None else p.weight)                       # default weight: the range's length
            cells.append(c)
            mass.append(w)
        flat_c = np.concatenate([np.atleast_1d(c) for c in cells])
        flat_w = np.concatenate([np.atleast_1d(m) for m in mass])
        requested = flat_w.sum()
        keep = np.ones(len(flat_c), bool)
        sh = solar_hour(flat_c, lon)
        keep &= (sh >= solar[0]) & (sh < solar[1])
        local = [c.replace(tzinfo=timezone.utc).astimezone(tzo) for c in flat_c.astype("datetime64[m]").astype(object)]
        for ex in self.exclude:
            keep &= ~self._excluded(ex, local, tzo, now)
        if not keep.any():
            raise WindowError(f"nothing is left of the window: the valid solar hours {solar[0]:.0f}-{solar[1]:.0f} h are {self._solar_in_local(lon, tzo, flat_c[0])} local on {local[0]:%Y-%m-%d}, and the exclusions removed the rest")
        cut = 1.0 - flat_w[keep].sum() / requested
        prob = flat_w[keep] / flat_w[keep].sum()
        cells_k = flat_c[keep]
        days = {}
        for c, pr in zip(np.array(local, dtype=object)[keep], prob):
            days[c.strftime("%Y-%m-%d")] = days.get(c.strftime("%Y-%m-%d"), 0.0) + float(pr)
        kind = "single" if len(cells_k) == 1 else ("triangular" if any(p.mode is not None for p in parts) else "uniform")
        first, last = describe_local(cells_k[0].astype(datetime), tzo), describe_local(cells_k[-1].astype(datetime), tzo)
        desc = (f"{first}" if kind == "single" else f"{kind} between {first} and {last}") + (f"; {100 * cut:.0f} % of the requested time was outside {solar[0]:.0f}-{solar[1]:.0f} h solar or excluded and was cut" if cut > 1e-9 else "")
        return ResolvedWindow(cells_k, prob, float(cut), kind, desc, days)

    @staticmethod
    def _excluded(ex, local, tzo, now):
        m = re.fullmatch(r"\s*(?:(\d{4}-\d{2}-\d{2})\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*-\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*", ex, re.I)
        if not m or _clock(m.group(2)) is None or _clock(m.group(3)) is None:
            raise WindowError(f"cannot read the exclusion {ex!r}: use '12:00-14:00' (every day) or '2027-06-18 09:00-10:00' (one day)")
        a, b = _clock(m.group(2)), _clock(m.group(3))
        out = np.zeros(len(local), bool)
        for i, t in enumerate(local):
            mins = t.hour * 60 + t.minute
            out[i] = a <= mins < b and (m.group(1) is None or t.strftime("%Y-%m-%d") == m.group(1))
        return out

    @staticmethod
    def _solar_in_local(lon, tzo, first_cell):
        d = first_cell.astype("datetime64[D]").astype(datetime)
        base = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        lo = base + timedelta(hours=SOLAR_LO - lon / 15.0)
        hi = base + timedelta(hours=SOLAR_HI - lon / 15.0)
        return f"{lo.astimezone(tzo):%H:%M}-{hi.astimezone(tzo):%H:%M}"

    def __repr__(self):
        return f"Window({self._spec!r}, earliest={self._earliest!r}, latest={self._latest!r}, exclude={self.exclude!r})"
