"""Injury impact model: turns an injury report into a point-spread adjustment.

Sportsbook lines already price injuries in, so this only feeds the rating
model used for games without a posted line (usually weeks more than a
month out). It is deliberately simple and transparent: each listed player
costs a position-based number of points, scaled by how certain the
absence is, with a cap per team. The numbers are conservative estimates of
starter-versus-backup value; a quarterback dominates, as it should.
"""
from __future__ import annotations

from dataclasses import dataclass

POSITION_POINTS = {
    "QB": 4.5,       # confirmed starter
    "QB2": 0.4,      # backup or unidentified quarterback
    "LT": 0.9, "RT": 0.7, "LG": 0.5, "RG": 0.5, "C": 0.6, "OL": 0.6, "OT": 0.8, "G": 0.5, "T": 0.8,
    "WR": 0.8, "TE": 0.5, "RB": 0.5, "FB": 0.1,
    "DE": 0.7, "DT": 0.5, "EDGE": 0.8, "OLB": 0.6, "ILB": 0.4, "LB": 0.5, "MLB": 0.5, "DL": 0.6, "NT": 0.4,
    "CB": 0.6, "S": 0.4, "FS": 0.4, "SS": 0.4, "DB": 0.4,
    "K": 0.4, "P": 0.2, "LS": 0.1, "PK": 0.4,
}
DEFAULT_POSITION_POINTS = 0.3
TEAM_CAP = 9.0

# How certain it is the player misses the next game.
STATUS_WEIGHT = {
    "out": 1.0,
    "injured reserve": 1.0,
    "ir": 1.0,
    "physically unable to perform": 1.0,
    "pup": 1.0,
    "suspension": 1.0,
    "suspended": 1.0,
    "doubtful": 0.85,
    "questionable": 0.4,
    "day-to-day": 0.3,
    "probable": 0.1,
    "active": 0.0,
}

# Long-term designations are assumed to persist; short-term ones fade.
LONG_TERM = {"injured reserve", "ir", "physically unable to perform", "pup", "suspension", "suspended"}
SHORT_TERM_HALF_LIFE_WEEKS = 2.0


@dataclass
class Injury:
    player: str
    position: str
    status: str
    detail: str = ""
    updated: str = ""

    @property
    def status_key(self) -> str:
        return self.status.strip().lower()

    @property
    def certainty(self) -> float:
        key = self.status_key
        if key in STATUS_WEIGHT:
            return STATUS_WEIGHT[key]
        for k, v in STATUS_WEIGHT.items():
            if k in key:
                return v
        return 0.0

    @property
    def points(self) -> float:
        """Points this player costs the team if absent this week (negative)."""
        pos = self.position.strip().upper()
        base = POSITION_POINTS.get(pos, DEFAULT_POSITION_POINTS)
        return -base * self.certainty

    def points_in(self, weeks_ahead: int) -> float:
        """Expected impact `weeks_ahead` weeks from now; short-term absences heal."""
        if self.status_key in LONG_TERM:
            return self.points
        fade = 0.5 ** (weeks_ahead / SHORT_TERM_HALF_LIFE_WEEKS)
        return self.points * fade


def team_impact(injuries: list[Injury], weeks_ahead: int = 0) -> float:
    """Total point adjustment for a team (0 or negative), capped."""
    total = sum(i.points_in(weeks_ahead) for i in injuries)
    return max(-TEAM_CAP, total)


def impacts_by_team(report: dict[str, list[Injury]], weeks_ahead: int = 0) -> dict[str, float]:
    return {team: team_impact(inj, weeks_ahead) for team, inj in report.items()}
