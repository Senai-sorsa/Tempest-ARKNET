"""Modes: which source answers, by lead time, and what each one can honestly claim.

past    valid time before now (ERA5 exists after about 6 days): the real record, corrected toward balloons; needs an ERA5 source (a local store or the network)
recent  within ~6 days of now (past or future): corrected newest forecasts / analyses        [source and correction not available yet: falls back, flagged]
week    0-7 days ahead: corrected forecasts                                                 [same]
medium  8-46 days ahead: recent data and forecasts used to correct the AI                    [same]
ai      beyond (and the fallback for everything above): the generator with calibrated ranges and the index forecast
`settings` (0-3) are the distribution settings, see api.distribution.
"""
from datetime import datetime, timezone

BOUNDS = dict(past=-6.0, recent=0.0, week=7.0, medium=46.0)  # lead in days (valid time minus now)
IMPLEMENTED = {"ai"}                                          # modes that always work; "past" is added when an ERA5 store is configured (api passes `available`)
NAMES = ("past", "recent", "week", "medium", "ai")


def lead_days(when_utc, now=None):
    """Valid time (naive UTC datetime) minus now (naive UTC datetime or ISO string), in days."""
    if now is None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
    elif isinstance(now, str):
        now = datetime.fromisoformat(now)
    return (when_utc - now).total_seconds() / 86400.0


def choose(lead, requested=None, available=None):
    """-> (mode used, quality flags). `requested` forces a mode (for tests); a mode without a source falls back to 'ai' and says so."""
    if requested is not None and requested not in NAMES:
        raise ValueError(f"mode must be one of {NAMES}")
    wanted = requested or ("past" if lead <= BOUNDS["past"] else "recent" if lead <= BOUNDS["recent"] else "week" if lead <= BOUNDS["week"]
                           else "medium" if lead <= BOUNDS["medium"] else "ai")
    if wanted in (IMPLEMENTED | set(available or ())):
        return wanted, ["nominal"]
    return "ai", ["fallback-mode", f"{wanted}-source-not-available"]
