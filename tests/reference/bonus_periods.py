#!/usr/bin/env python3
"""
Build the birthday / release-anniversary bonus calendar for every visible song.

Rules
-----
* Member birthday bonus : +2% per artist code, from 3 days before to 3 days
  after the birthday (7 days, inclusive). Skipped when the artist has
  bonusBirthdayUse == false or artistType == 4. A null bonusBirthday is
  treated as timestamp 0 (Jan 1).
* Release anniversary   : +3%, same -3/+3 day window around the release date,
  from the release year on.
* Several artist codes of the same person (e.g. IRENE Vocal / Dance / Rhythm)
  are merged into one entry, with their percentages added together.
* Overlaps (anniversary + birthdays, or several birthdays) are split into
  separate periods, each listing exactly which bonuses are active in it.
* Feb 29 events are skipped unless that year is a leap year.
* isHidden songs are ignored.
* Besides the per-song view, a flat date-ordered "calendar" lists every day on
  which something changes: a bonus starting, the total % changing, or ending
  (an "end" event is dated on the LAST day the bonus is active).

Usage
-----
    python bonus_periods.py [--data-dir DIR] [--year YYYY] [--out FILE]
"""

import argparse
import calendar
import json
from collections import OrderedDict, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# Timestamps in the data are local midnight in Korea (incl. historical DST,
# e.g. 1987), so convert with the real tz database instead of a fixed +9.
TZ = ZoneInfo("Asia/Seoul")

WINDOW_DAYS = 3
BIRTHDAY_PCT = 2
ANNIVERSARY_PCT = 3
EXCLUDED_ARTIST_TYPE = 4


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def load(path):
    """Load a data file as {str(code): entry}.

    Accepts either the original list-of-objects layout (each with a "code")
    or a dict already keyed by code.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return {str(item["code"]): item for item in data}
    return {str(k): v for k, v in data.items()}


def ms_to_date(ms):
    return datetime.fromtimestamp(ms / 1000, TZ).date()


def locale_text(locale, code, fallback=None):
    """Resolve a locale code to English text (falls back to Korean / fallback)."""
    entry = locale.get(str(code))
    if entry:
        return entry.get("enUS") or entry.get("koKR") or fallback
    return fallback


def anniversary_in_year(d, year):
    """Same month/day as d in `year`, or None for a Feb 29 in a non-leap year."""
    if d.month == 2 and d.day == 29 and not calendar.isleap(year):
        return None
    return date(year, d.month, d.day)


def window(center):
    return center - timedelta(days=WINDOW_DAYS), center + timedelta(days=WINDOW_DAYS)


def group_info(groups, locale, code):
    g = groups.get(str(code))
    name = None
    if g:
        name = locale_text(locale, g.get("localeName"), g.get("analyticsData"))
    return {"code": code, "name": name or g and g.get("analyticsData")}


# --------------------------------------------------------------------------- #
# core
# --------------------------------------------------------------------------- #
def build_song_periods(song, artists, groups, locale, year):
    year_start, year_end = date(year, 1, 1), date(year, 12, 31)
    release = ms_to_date(song["releaseDate"])
    song_group = song["groupData"]

    # ---- collect bonus sources, merging same-person artist codes ----------- #
    people = OrderedDict()  # (name, birth date) -> info
    codes = json.loads(song["artistCode"]) if song.get("artistCode") else []
    for code in dict.fromkeys(codes):  # de-dupe, keep order
        a = artists.get(str(code))
        if not a:
            continue
        if not a.get("bonusBirthdayUse") or a.get("artistType") == EXCLUDED_ARTIST_TYPE:
            continue
        # null bonusBirthday defaults to timestamp 0 (-> 1970-01-01, i.e. Jan 1)
        birth = ms_to_date(a["bonusBirthday"] or 0)
        name = locale_text(locale, a["localeName"], a.get("analyticsData"))
        key = (name, birth)
        p = people.setdefault(
            key,
            {
                "name": name,
                "birth": birth,
                "codes": [],
                "percent": 0,
                "group_code": a["group"],
            },
        )
        p["codes"].append(code)
        p["percent"] += BIRTHDAY_PCT

    # ---- build intervals (inclusive) clipped to the target year ------------ #
    # neighbouring years are scanned so Dec/Jan windows spill over correctly.
    intervals = []  # (start, end, bonus_key)
    for y in (year - 1, year, year + 1):
        for key, p in people.items():
            c = anniversary_in_year(p["birth"], y)
            if c:
                intervals.append((*window(c), ("member", key)))
        if y >= release.year:
            c = anniversary_in_year(release, y)
            if c:
                intervals.append((*window(c), ("release", y - release.year)))

    clipped = []
    carried_in, carried_out = set(), set()  # windows crossing the year boundary
    for s_orig, e_orig, k in intervals:
        s, e = max(s_orig, year_start), min(e_orig, year_end)
        if s <= e:
            clipped.append((s, e, k))
            if s_orig < year_start:
                carried_in.add(k)
            if e_orig > year_end:
                carried_out.add(k)
    if not clipped:
        return []

    # ---- split into non-overlapping segments at every start / end+1 -------- #
    cuts = sorted(
        {s for s, _, _ in clipped} | {e + timedelta(days=1) for _, e, _ in clipped}
    )
    periods = []
    for left, right in zip(cuts, cuts[1:]):
        seg_end = right - timedelta(days=1)
        active = [k for s, e, k in clipped if s <= left and seg_end <= e]
        if not active:
            continue

        bonuses, total = [], 0
        for kind, val in active:
            if kind == "release":
                bonuses.append(
                    {
                        "type": "release_anniversary",
                        "percent": ANNIVERSARY_PCT,
                        "anniversary": val,
                        "releaseDate": release.isoformat(),
                    }
                )
                total += ANNIVERSARY_PCT
            else:
                p = people[val]
                b = {
                    "type": "member_birthday",
                    "name": p["name"],
                    "percent": p["percent"],
                    "birthday": p["birth"].strftime("%m-%d"),
                    "artistCodes": p["codes"],
                }
                # artist belongs to a different group than the song's group
                if p["group_code"] != song_group:
                    b["group"] = group_info(groups, locale, p["group_code"])
                bonuses.append(b)
                total += p["percent"]

        periods.append(
            {
                "start": left.isoformat(),
                "end": seg_end.isoformat(),
                "startsInPreviousYear": left == year_start
                and any(k in carried_in for k in active),
                "endsInNextYear": seg_end == year_end
                and any(k in carried_out for k in active),
                "days": (seg_end - left).days + 1,
                "totalPercent": total,
                "bonuses": bonuses,
            }
        )
    return periods


def bonus_key(b):
    if b["type"] == "release_anniversary":
        return ("release_anniversary",)
    return ("member_birthday", b["name"], b["birthday"])


def build_calendar(songs_out):
    """Flat, date-ordered list of everything that changes on each day."""
    days = defaultdict(list)
    for song in songs_out:
        base = {
            "songCode": song["code"],
            "songName": song["name"],
            "group": song["group"],
        }
        periods = song["periods"]
        for i, p in enumerate(periods):
            prev = periods[i - 1] if i else None
            nxt = periods[i + 1] if i + 1 < len(periods) else None
            start = date.fromisoformat(p["start"])
            end = date.fromisoformat(p["end"])

            # --- what happens when this period begins -------------------- #
            if p["startsInPreviousYear"]:
                days[p["start"]].append(
                    {
                        **base,
                        "event": "ongoing",  # already active before Jan 1
                        "fromPercent": p["totalPercent"],
                        "toPercent": p["totalPercent"],
                        "added": [],
                        "removed": [],
                        "activeBonuses": p["bonuses"],
                    }
                )
            elif prev and date.fromisoformat(prev["end"]) + timedelta(days=1) == start:
                before = {bonus_key(b): b for b in prev["bonuses"]}
                after = {bonus_key(b): b for b in p["bonuses"]}
                days[p["start"]].append(
                    {
                        **base,
                        "event": "change",
                        "fromPercent": prev["totalPercent"],
                        "toPercent": p["totalPercent"],
                        "added": [b for k, b in after.items() if k not in before],
                        "removed": [b for k, b in before.items() if k not in after],
                        "activeBonuses": p["bonuses"],
                    }
                )
            else:
                days[p["start"]].append(
                    {
                        **base,
                        "event": "start",
                        "fromPercent": 0,
                        "toPercent": p["totalPercent"],
                        "added": p["bonuses"],
                        "removed": [],
                        "activeBonuses": p["bonuses"],
                    }
                )

            # --- what happens after this period (only if nothing follows) - #
            if not p["endsInNextYear"] and not (
                nxt and date.fromisoformat(nxt["start"]) == end + timedelta(days=1)
            ):
                days[p["end"]].append(
                    {
                        **base,
                        "event": "end",
                        "fromPercent": p["totalPercent"],
                        "toPercent": 0,
                        "added": [],
                        "removed": p["bonuses"],
                        "activeBonuses": [],
                    }
                )

    order = {"ongoing": 0, "start": 1, "change": 2, "end": 3}
    calendar_out = []
    for d in sorted(days):
        ev = sorted(
            days[d],
            key=lambda e: (order[e["event"]], e["songName"] or "", e["songCode"]),
        )
        calendar_out.append(
            {
                "date": d,
                "counts": {k: sum(1 for e in ev if e["event"] == k) for k in order},
                "events": ev,
            }
        )
    return calendar_out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=".")
    ap.add_argument("--year", type=int, default=date.today().year)
    ap.add_argument("--view", choices=["songs", "calendar", "both"], default="both")
    ap.add_argument("--out", default=None, help="write JSON here (default: stdout)")
    args = ap.parse_args()

    d = Path(args.data_dir)
    music = load(d / "MusicData.json")
    artists = load(d / "ArtistData.json")
    groups = load(d / "GroupData.json")
    locale = load(d / "LocaleData.json")

    songs_out = []
    for code, song in music.items():
        if song.get("isHidden"):
            continue
        periods = build_song_periods(song, artists, groups, locale, args.year)
        if not periods:
            continue
        songs_out.append(
            {
                "code": song["code"],
                "name": locale_text(
                    locale, song["localeName"], song.get("analyticsData")
                ),
                "group": group_info(groups, locale, song["groupData"]),
                "releaseDate": ms_to_date(song["releaseDate"]).isoformat(),
                "periods": periods,
            }
        )

    result = {
        "year": args.year,
        "isLeapYear": calendar.isleap(args.year),
        "rules": {
            "memberBirthdayPercentPerArtistCode": BIRTHDAY_PCT,
            "releaseAnniversaryPercent": ANNIVERSARY_PCT,
            "windowDaysBeforeAndAfter": WINDOW_DAYS,
        },
        "songCount": len(songs_out),
    }
    if args.view in ("songs", "both"):
        result["songs"] = songs_out
    if args.view in ("calendar", "both"):
        result["calendar"] = build_calendar(songs_out)

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
