"""Turn the four downloaded public files into compact parquet files (no scoring happens here).

Usage: python3 -I -B tools/prepare.py <raw dir> <work dir>
<raw dir> holds criteo/, asos/, retail/, hillstrom/ as fetched by tools/get_data.py.
"""
import sys
from pathlib import Path

import duckdb

raw, work = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
work.mkdir(parents=True, exist_ok=True)
con = duckdb.connect()
con.execute("SET threads=2")
con.execute("SET memory_limit='1200MB'")

# Criteo uplift v2.1: 13,979,592 users; streamed by DuckDB, never loaded whole.
crit = raw / "criteo" / "criteo-research-uplift-v2.1.csv.gz"
out = work / "criteo.parquet"
if not out.exists():
    cols = ", ".join(f"CAST(f{i} AS FLOAT) AS f{i}" for i in range(12))
    con.execute(f"""COPY (SELECT row_number() OVER () - 1 AS rid, {cols},
                    CAST(treatment AS TINYINT) AS treatment, CAST(conversion AS TINYINT) AS conversion,
                    CAST(visit AS TINYINT) AS visit, CAST(exposure AS TINYINT) AS exposure
                    FROM read_csv('{crit}', header=true))
                 TO '{out}' (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 500000)""")
print("criteo rows", con.execute(f"SELECT count(*) FROM '{out}'").fetchone()[0])

# ASOS digital experiments: already small.
asos = raw / "asos" / "asos_digital_experiments_dataset.csv"
out = work / "asos.parquet"
if not out.exists():
    con.execute(f"COPY (SELECT * FROM read_csv_auto('{asos}')) TO '{out}' (FORMAT parquet)")
print("asos rows", con.execute(f"SELECT count(*) FROM '{out}'").fetchone()[0])

# Hillstrom e-mail test.
hill = raw / "hillstrom" / "hillstrom.csv"
out = work / "hillstrom.parquet"
if not out.exists():
    con.execute(f"COPY (SELECT * FROM read_csv_auto('{hill}')) TO '{out}' (FORMAT parquet)")
print("hillstrom rows", con.execute(f"SELECT count(*) FROM '{out}'").fetchone()[0])

# Online Retail II: two yearly sheets in one workbook, read row by row (openpyxl, read-only mode).
out = work / "retail.parquet"
if not out.exists():
    import csv
    import openpyxl
    tmp = work / "retail.csv"
    wb = openpyxl.load_workbook(raw / "retail" / "online_retail_II.xlsx", read_only=True)
    with tmp.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["invoice", "stock_code", "quantity", "invoice_date", "price", "customer_id", "country"])
        for ws in wb.worksheets:
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i == 0:
                    continue
                inv, code, _desc, qty, date, price, cust, country = row[:8]
                w.writerow([inv, code, qty, date.isoformat() if date else "", price,
                            "" if cust is None else int(cust), country])
    con.execute(f"""COPY (SELECT CAST(invoice AS VARCHAR) AS invoice, CAST(stock_code AS VARCHAR) AS stock_code,
                    CAST(quantity AS INTEGER) AS quantity, CAST(invoice_date AS TIMESTAMP) AS invoice_date,
                    CAST(price AS DOUBLE) AS price, TRY_CAST(customer_id AS INTEGER) AS customer_id, country
                    FROM read_csv('{tmp}', header=true, all_varchar=true))
                 TO '{out}' (FORMAT parquet)""")
    tmp.unlink()
print("retail rows", con.execute(f"SELECT count(*) FROM '{out}'").fetchone()[0])
