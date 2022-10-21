import datetime
import typing


def date_range(
        start: datetime.date,
        end: datetime.date,
        step: datetime.timedelta = datetime.timedelta(1),
) -> typing.Generator[datetime.date, None, None]:
    current = start
    while current <= end:
        yield current
        current += step


# noinspection SpellCheckingInspection
def try_strptime(
        data: str, *fmts: str, default: datetime.datetime = None
) -> datetime.datetime:
    for fmt in fmts:
        # noinspection PyBroadException
        try:
            dt = datetime.datetime.strptime(data, fmt)
        except Exception:
            continue
        else:
            return dt
    return default
