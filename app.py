#!/usr/bin/env python3

# DAILY SALES SUMMARY AUTOMATION
#
# 1. File format
# - File content specification: <Outlet Lot>|<Business Date>|<Gross Sales Amount>
# - File naming convention: <Outlet Lot>_<Business Date>.txt
#   <Outlet Lot> is tenant lot no provided by the mall without spaces and -.
#   <Business Date> is business date of the sales with format DDMMYYYY.
#   <Gross Sales Amount> is gross sales amount of the day, minus all discounts,
# - Currency format with two decimal points without commas and symbols.
# - Currency unit in RM (Ringgit Malaysia).
#
# 2. File posting
# - Submission timeframe: two hours after business closure for each day.
# - The file will uploaded to one specific sFTP account.
# - Program will upload sales with "0.00" amount when outlet closure or no sales occure.
# - Program allow backdate upload sales file when required by Mall Management.
#
# Requirements:
# - .env
# - tenant.txt


import requests
from datetime import datetime
from dateutil import tz

import paramiko

import os
from dotenv import load_dotenv

load_dotenv()

from argparse import ArgumentParser

cli_parser = ArgumentParser(
    description="Daily sales data submission program",
    epilog="Thank you!",
)
cli_parser.add_argument(
    "--date",
    nargs="?",
    default=datetime.now().strftime("%Y-%m-%d"),
    const=datetime.now().strftime("%Y-%m-%d"),
    metavar="YYYY-MM-DD",
    help="manual defining date, default is today",
)
cli_parser.add_argument(
    "-k", "--keep", action="store_true", help="do not remove sale file after submit"
)
cli_parser.add_argument(
    "-s", "--submit", action="store_true", help="submit sale file to mall's server"
)
args = cli_parser.parse_args()


import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %X",
)


ENV = "production"
BASEURL = "https://api.loyverse.com/v1.0"


def import_tenant(fname: str = "tenant.txt") -> list:
    """Import tenant information from file"""
    with open(fname, "r") as file:
        return [tuple(line.strip().split("|")) for line in file.readlines()]


def _fetch(item: str, **params) -> dict | None:
    """Get raw data"""
    r = requests.get(
        url="{}/{}".format(BASEURL, item),
        headers={
            "Authorization": "Bearer {}".format(
                os.getenv("TOKEN", "")
                if ENV == "production"
                else os.getenv("TEST_TOKEN", "")
            ),
            "Content-Type": "application/json",
        },
        params={**params},
    )
    if r.status_code != 200:
        logging.error("fetch {} status code {}".format(item, r.status_code))
        return
    return r.json()


def get_receipts(tenant: str, date: str, timezone: str = "Asia/Kuala_Lumpur") -> list:
    """Get transaction data according to store name and date"""
    what = "receipts"
    store_id = get_store_id(tenant=tenant)
    dt = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=tz.gettz(timezone))
    date_min = dt.astimezone(tz=tz.UTC)
    date_max = dt.replace(hour=23, minute=59, second=59).astimezone(tz=tz.UTC)
    params = {
        "store_id": str(store_id),
        "created_at_min": date_min.strftime("%Y-%m-%dT%XZ"),
        "created_at_max": date_max.strftime("%Y-%m-%dT%XZ"),
        "limit": 250,  # maximum allowed
    }
    r = _fetch(item=what, **params)
    data = r.get(what, [])
    cursor = r.get("cursor")
    while cursor:
        params.update({"cursor": cursor})
        r = _fetch(item=what, **params)
        data.extend(r.get(what, []))
        cursor = r.get("cursor")
    return data


def get_store_id(tenant: str) -> str | None:
    """Get store_id by store name"""
    what = "stores"
    r = _fetch(item=what).get(what, [])
    stores = [s.get("id") for s in r if s.get("name") == tenant]
    if len(stores) >= 1:
        return stores[0]
    else:
        logging.error("cannot find store")
        return


def _money_factor(item: dict) -> int:
    """Calculation factor, sale (+) or refund (-)"""
    return 1 if item.get("receipt_type") == "SALE" else -1


def _money_total(data: list) -> list:
    """Extract net sales from rawdata (payment = price - discount)"""
    return [item.get("total_money", 0) * _money_factor(item) for item in data]


def get_total_money(data: list, decimal: int = 2) -> float:
    """Calculate total net sales"""
    money = _money_total(data)
    return round(sum(money), decimal)


def gross_sales_amount(tenant: str, date: str, lot: str) -> tuple:
    """Extract Gross Sales Amount"""
    datefmt = datetime.strptime(date, "%Y-%m-%d").strftime("%d%m%Y")
    data = get_receipts(tenant=tenant, date=date)
    sales = get_total_money(data)
    return (lot, datefmt, "{0:.2f}".format(sales))


def generate_file_name(data: tuple | list) -> str:
    """Generate sale file name"""
    return "{}.txt".format("_".join(data[:-1]))


def generate_file_content(data: tuple | list) -> str:
    """Generate sale file content"""
    return "|".join(data)


def export_sales(data: tuple | list) -> None:
    """Export sales data to a txt file"""
    f = generate_file_name(data)
    t = generate_file_content(data)
    with open(f, "w") as file:
        file.write(t)
        logging.info("export {} to {}".format(t, f))


def send(localpath: str, remotepath: str) -> None:
    """Sales file submission.
    Need to initialize ssh connection first to generate host key
    """
    with paramiko.SSHClient() as ssh:
        try:
            ssh.load_system_host_keys()
            ssh.connect(
                hostname=os.getenv("FTP_HOST", "localhost"),
                port=int(os.getenv("PORT", 22)),
                username=os.getenv("FTP_USERNAME"),
                password=os.getenv("FTP_PASSWORD"),
            )
            logging.info(f"connecting to remote sftp server")
            # sftp = ssh.open_sftp()
            try:
                tp = ssh.get_transport()
                if tp:
                    sftp = paramiko.SFTPClient.from_transport(tp)
                    sftp.put(localpath, remotepath)
                    logging.info(f"submit {localpath} to remotepath")
                    sftp.close()
            except Exception as e:
                logging.error(f"{type(e).__name__}: {str(e)}")
                raise e
        except paramiko.ssh_exception.SSHException as e:
            logging.error(f"{str(e)}")
        except Exception as e:
            logging.error(f"{type(e).__name__}: {str(e)}")
            raise e


def delete(fname: str) -> None:
    if os.path.exists(fname):
        os.remove(fname)
        logging.info(f"delete {fname} in localpath")


def application(
    date: str = datetime.now().strftime("%Y-%m-%d"),
    submit: bool = True,
    rmafter: bool = True,
) -> None:
    """Main application"""
    tenants = import_tenant()
    for name, code in tenants:
        data = gross_sales_amount(tenant=name, date=date, lot=code)
        export_sales(data)
        f = generate_file_name(data)
        try:
            if submit:
                send(f, f)
        except Exception as e:
            if rmafter:
                delete(f)
        finally:
            if rmafter:
                delete(f)


if __name__ == "__main__":
    application(date=args.date, submit=args.submit, rmafter=(not args.keep))
