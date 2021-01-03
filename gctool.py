"""
tools for manipulating gnucash xml books
(make sure to have a backup!)
"""
import itertools
import operator as op
import pprint
import re
import sys
from datetime import datetime
from decimal import Decimal

from lxml import etree


def main(gcxml_path):
    "load a book, do some work, save the book"
    book = Book.load(gcxml_path)
    with open("initial-summary", "w") as f:
        pprint.pprint(book.summary(), stream=f)
    make_changes(book)
    with open("final-summary", "w") as f:
        pprint.pprint(book.summary(), stream=f)
    book.save(gcxml_path)


def make_changes(book):
    "transform splits"
    splits = list(book.splits(
        book.match_account("E:Utilities:Phone/Internet"),
    ))
    changes = [
        ("Golan", "E:Utilities:Cellular Service"),
    ]
    funcpairs = []
    for desc, acct in changes:
        set_account = book.set_account(acct)
        if set_account:
            funcpairs.append((book.match_description(desc), set_account))
        else:
            print(f"not found: {acct}")
    count = 0
    for s in splits:
        for test_desc, set_account in funcpairs:
            if test_desc(s):
                set_account(s)
                count += 1
                continue
    print(f"changed {count} splits")


class Book:
    """
    gnucash xml book
    """
    @classmethod
    def load(cls, path):
        "load book from xml file"
        with open(path) as f:
            return cls(etree.parse(f))

    def save(self, path):
        "save book to xml file"
        kwargs = {
            'encoding': 'utf-8',
            'xml_declaration': True,
            'pretty_print': True,
        }
        with open(path, "wb") as f:
            f.write(etree.tostring(self.doc, **kwargs))

    def __init__(self, doc):
        self.doc = doc
        self.root = doc.getroot()
        self.ns = {"namespaces": self.root.nsmap}
        self.account_dict = self._account_dict()

    def summary(self):
        "summarize book splits by account"
        key = op.itemgetter("account")
        splits = sorted(map(self.splitdict, self.splits()), key=key)
        return {
            acct: splits_summary(group)
            for acct, group in itertools.groupby(splits, key)
        }

    def set_account(self, fullname):
        "construct split modifier to set account"
        search_account = self.account_dict.get(fullname)
        if not search_account:
            return
        def set_account(split):
            account_el = split.find("split:account", **self.ns)
            account_el.text = search_account
        return set_account

    def splits(self, *search):
        "get all splits matching search predicates"
        elempath = "gnc:book/gnc:transaction/trn:splits/trn:split"
        allsplits = self.root.findall(elempath, **self.ns)
        pred = lambda s: all(p(s) for p in search)
        return filter(pred, allsplits)

    def splitcsv(self, split):
        "csv representation of split"
        fields = op.itemgetter("date", "description", "memo", "account", "value")
        return ','.join(map(str, fields(self.splitdict(split))))

    def splitdict(self, split):
        "python dict of split data"
        field_paths = [
            ("id", "split:id", None),
            ("date", "../../trn:date-posted/ts:date", parse_date),
            ("description", "../../trn:description", None),
            ("memo", "split:memo", None),
            ("account", "split:account", self.account_dict.get),
            ("reconciled-state", "split:reconciled-state", None),
            ("value", "split:value", parse_value),
        ]
        field = lambda p: split.findtext(p, **self.ns)
        conv = lambda c, f: c(f) if c else f
        return {k: conv(c, field(p)) for k, p, c in field_paths}

    def match_account(self, fullname):
        "construct predicate to test split against account fullname"
        search_account = self.account_dict.get(fullname)
        account = lambda s: s.findtext("split:account", **self.ns)
        return lambda s: account(s) == search_account

    def match_memo(self, pattern):
        "construct predicate to test split against memo"
        memo = lambda s: s.findtext("split:memo", **self.ns)
        return lambda s: re.search(pattern, memo(s))

    def match_description(self, pattern):
        "construct predicate to test split against transaction description"
        description = lambda s: s.findtext("../../trn:description", **self.ns)
        return lambda s: re.search(pattern, description(s))

    def _account_dict(self):
        "construct dict mapping id -> account fullname and fullname -> id"
        actid = lambda a: a.findtext("act:id", **self.ns)
        actname = lambda a: a.findtext("act:name", **self.ns)
        actparent = lambda a: a.findtext("act:parent", **self.ns)

        xpath = "gnc:book/gnc:account"
        accounts = self.root.xpath(xpath, **self.ns)
        idmap = {actid(a): a for a in accounts}

        def fullpath(account):
            parent_id = actparent(account)
            if parent_id:
                parent = idmap.get(parent_id)
                if parent is not None:
                    return fullpath(parent) + [account]
            return []

        account_dict = {}
        for account in accounts:
            account_id = actid(account)
            path = fullpath(account)
            account_name = ':'.join(actname(a) for a in path)
            account_dict[account_name] = account_id
            account_dict[account_id] = account_name
        return account_dict


def splits_summary(splits):
    "summarize split dicts"
    splits = list(splits)
    total = sum(s["value"] for s in splits)
    count = len(splits)
    return (count, total)


def parse_date(ts):
    "parse timestamp str into date"
    return datetime.strptime(ts.split()[0], "%Y-%m-%d").date()


def parse_value(vs):
    "parse value str into decimal"
    num, den = map(Decimal, vs.split("/"))
    return num / den


if __name__ == "__main__":
    main(sys.argv[1])
