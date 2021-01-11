"""
higher-level functions for extracting account data from gnucashxml Book objects
"""
import pandas as pd

from . import gnucashxml


class GCReader:
    "class for extracting splits from gnucash xml book by account and daterange"
    def __init__(self, config, gnucash_path):
        self.config = config
        self.gcbook = gnucashxml.from_filename(gnucash_path)

    def sections(self):
        "report sections"
        return [(sd, self.section_data(sd)) for sd in self.config["sections"]]

    def section_data(self, secdef):
        "aggregate data for section as a pandas DataFrame"
        period = secdef["agg_period"]
        accounts = secdef["accounts"]
        agg = lambda ds: ds.resample(pdfreq(period)).sum()
        data = [(n, self.account_data(n)) for n in accounts]
        aggdata = {n: agg(df) for n, df in data if df is not None}
        return pd.DataFrame(aggdata).fillna(0)

    def account_data(self, fullname):
        "get account splits for given range as a pandas data Series"
        splits = list(self.get_account_splits(fullname) or [])
        if not splits:
            return
        return pd.DataFrame(
            [(s.transaction.date, self.get_split_amount(s)) for s in splits],
            columns=["date", fullname],
        ).set_index("date")[fullname]

    def get_account_splits(self, fullname):
        "apply filter to all splits in account"
        account = self.find_account_by_fullname(fullname)
        if account is None:
            return
        predicates = list(filter(None, [
            daterange_predicate(self.config["daterange"]),
        ]))
        return (s for s in account.get_all_splits() if all(p(s) for p in predicates))

    def get_split_amount(self, split):
        "get split amount, performing currency conversion"
        currency = split.account.commodity.name
        if currency == self.config["currency"]:
            conversion_rate = 1.0
        else:
            year = split.transaction.date.year
            conversion_rate = self.config["exchange_rates"][currency][year]
        return float(split.quantity) * conversion_rate

    def find_account_by_fullname(self, fullname):
        "get account matching fullname"
        for account in self.gcbook.accounts:
            if account.fullname() == fullname:
                return account


def daterange_predicate(daterange):
    "construct a test for daterange"
    try:
        start, end = daterange
    except TypeError:
        return None
    return lambda split: start <= split.transaction.date.date() <= end


def pdfreq(period):
    "get pandas frequency “offset alias” for aggregation period"
    p = period.lower()
    if "quarter" in p:
        return "QS"
    if "year" in p:
        return "YS"
    return "MS"
