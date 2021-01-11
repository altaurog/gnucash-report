"""
This is an attempt to automate generating a useful spreadsheet report
from a gnucash xml file

config structure:
    daterange: tuple of dates
    sections: list of dicts
        title: str
        agg_period: month, quarter, or year
        accounts: list of str, account fullnames
"""

def report(config, reader):
    "extract timeseries data according to config"
    sections = reader.sections()
    sheets = [(sd["title"], section_sheet(sd, df)) for sd, df in sections]
    summary = [("summary", summary_sheet(sections))]
    totals = [("monthly totals", totals_sheet(sections))]
    return dict(summary + totals + sheets)


def summary_sheet(sections):
    "construct sheet data for yearly rollup summary of all sections"
    for secdef, df in sections:
        agg = df_round(df.resample("Y").mean())
        title = secdef["title"]
        period = secdef["agg_period"]
        year = lambda ts: ts.year
        yield [f"{title} ({period})", *map(year, agg.index)]
        for fullname in secdef["accounts"]:
            if fullname in agg:
                yield [fullname, *agg[fullname]]
        yield ["total", *agg.sum(axis=1)]
        yield []


def totals_sheet(sections):
    "construct sheet data for yearly section totals"
    for i, (secdef, df) in enumerate(sections):
        agg = df_round(df.resample("Y").sum() / 12.0)
        title = secdef["title"]
        year = lambda ts: ts.year
        if not i:
            yield ["year", *map(year, agg.index)]
        yield [title, *agg.sum(axis=1)]


def section_sheet(secdef, df):
    "construct sheet data for section"
    month = lambda ts: f"{ts.month}/{ts.year}"
    yield ["", *map(month, df.index)]
    for fullname in secdef["accounts"]:
        if fullname in df:
            yield [fullname, *df_round(df[fullname])]


def df_round(df):
    "round values in df"
    return df.round().astype('int32')
