"""
top-level functions
"""
import pyexcel

from . import gcreader, report


def main(config, gnucash_path, output_path):
    "read gnucash data and create report spreadsheet per config"
    reader = gcreader.GCReader(gnucash_path, daterange=config["daterange"])
    data = report.report(config, reader)
    pyexcel.save_book_as(dest_file_name=output_path, bookdict=data)
