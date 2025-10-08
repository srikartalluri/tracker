#!/usr/bin/env python3
import argparse
from plaid.api import plaid_api
import os
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from dotenv import load_dotenv
load_dotenv()
from datetime import date, timedelta
from dataclasses import asdict
from utils import *
from argparse import RawTextHelpFormatter
from guess_categorize import guess_category
import json


MY_CARDS_VALS = [CardType.CHASEPRIME.value, CardType.BILT.value, CardType.VENMO.value]

CARD_TYPE_MAP = {
    CardType.CHASEPRIME.value: CardType.CHASEPRIME,
    CardType.BILT.value: CardType.BILT,
    CardType.VENMO.value: CardType.VENMO,
}

with open("./db/categories.json", "r") as file:
    categories = json.load(file)

# print(categories)

idx_category = {i:cat for i, cat in enumerate(categories)}
category_idx = {cat:i for i, cat in enumerate(categories)}




def get_dates_from_args(args) -> tuple[date, date]:

    if args.from_to_date:
        try:
            start_date = date.fromisoformat(args.from_to_date[0])
            end_date = date.fromisoformat(args.from_to_date[1])
        except Exception as e:
            print("Error parsing dates. Please use YYYY-MM-DD format.")
            exit(1)
        if start_date > end_date:
            print("Error: Start date cannot be after end date.")
            exit(1)
        return (start_date, end_date)
    
    if args.last_month:
        today = date.today()
        start_date = today - timedelta(days=31)
        end_date = today
        return (start_date, end_date)

    if args.last_week:
        today = date.today()
        start_date = today - timedelta(days=7)
        end_date = today
        return (start_date, end_date)
    
    else:
        today = date.today()
        start_date = today.replace(day=3)
        end_date = today
        return (start_date, end_date)
    

def do_update(args):
    print(args)
    db = TinyDB(DB_PATH)
    if args.filter_by:
        cards_to_do = [CARD_TYPE_MAP[args.filter_by]]
    else:
        cards_to_do = list(CardType)

    for card in cards_to_do:
        print(f"Updating transactions for {card.name}...")
        update_db_from_plaid(card, get_all=args.get_all, replace_if_exists=args.force)

    db.close()

def do_get(args):
    if args.filter_by:
        cards_to_do = [CARD_TYPE_MAP[args.filter_by]]
    else:
        cards_to_do = list(CardType)


    (start_date, end_date) = get_dates_from_args(args)
    print(f"Getting transactions from {start_date} to {end_date} for cards: {[c.name for c in cards_to_do]}")

    all_transactions = []
    for card in cards_to_do:
        all_transactions.extend(get_transactions_between_dates(start_date, end_date, card))

    print(f"Found {len(all_transactions)} transactions.")

    all_transactions.sort(key=lambda x: x.datetime, reverse=True)

    
    for tr in all_transactions:
        if args.category and tr.my_category != args.category:
            continue

        print_time = datetime.fromtimestamp(tr.datetime).isoformat()
        print_amt = f"{tr.amount:<10.2f}"
        print_my_category = f"{tr.my_category:<20}" if tr.my_category else " " * 20
        print_name = f"{tr.name:<60}"
        print(print_time, print_my_category, print_amt, print_name)

def categorize_transaction(tr: MyTransaction, cur, total) -> str:

    print("--------------------------------")
    print(f"Categorizing transaction {cur}/{total}:")
    print(datetime.fromtimestamp(tr.datetime).isoformat(), tr.amount, tr.name, tr.merchant_name)
    guessed_category = guess_category(tr.name, tr.merchant_name)
    print(f"Guessed category: {guessed_category}")

    print("Available categories:")
    for k,v in idx_category.items():
        print(f"{k}: {v}")
    
    user_input = input(f"Enter category index (or press Enter to accept '{guessed_category}', or 's' to skip): ").strip()
    if user_input.lower() == 's':
        print("Skipping categorization for this transaction.")
        return "Uncategorized"
    elif user_input == '':
        if guessed_category:
            selected_category = guessed_category
            return selected_category
        else:
            print("No guessed category available. Skipping categorization for this transaction.")
            return "Uncategorized"
    else:
        try:
            idx = int(user_input)
            if idx in idx_category:
                selected_category = idx_category[idx]
                return selected_category
            else:
                print("Invalid index. Skipping categorization for this transaction.")
                return "Uncategorized"
        except ValueError:
            print("Invalid input. Skipping categorization for this transaction.")
            return "Uncategorized"


def do_categorize(args):
    print(args)
    db = TinyDB(DB_PATH)

    if args.filter_by:
        cards_to_do = [CARD_TYPE_MAP[args.filter_by]]
    else:
        cards_to_do = list(CardType)
    
    (start_date, end_date) = get_dates_from_args(args)
    
    force_categorize = args.force
    if force_categorize:
        print("Force categorization enabled: will categorize all transactions in the date range, even if already categorized.")

    all_transactions = []
    for card in cards_to_do:
        all_transactions.extend(get_transactions_between_dates(start_date, end_date, card, get_only_uncategorized=not force_categorize))
    
    all_transactions.sort(key=lambda x: x.datetime, reverse=True)
    print(f"Found {len(all_transactions)} transactions to categorize.")

    for i in range(len(all_transactions)):
        tr = all_transactions[i]
        new_category = categorize_transaction(tr, i+1, len(all_transactions))
        print(f"Selected category: {new_category}")

        if new_category != "Uncategorized":
            tr.my_category = new_category
            Transaction = Query()
            db.update(asdict(tr), Transaction.transaction_id == tr.transaction_id)


def do_summary(args):
    if args.filter_by:
        cards_to_do = [CARD_TYPE_MAP[args.filter_by]]
    else:
        cards_to_do = list(CardType)


    (start_date, end_date) = get_dates_from_args(args)
    # print(f"Summarizing transactions from {start_date} to {end_date} for cards: {[c.name for c in cards_to_do]}")

    all_transactions = []
    for card in cards_to_do:
        all_transactions.extend(get_transactions_between_dates(start_date, end_date, card))

    print(f"Found {len(all_transactions)} transactions.")

    # all_transactions.sort(key=lambda x: x.datetime, reverse=True)

    
    # for tr in all_transactions:
    #     print_time = datetime.fromtimestamp(tr.datetime).isoformat()
    #     print_amt = f"{tr.amount:<10.2f}"
    #     print_my_category = f"{tr.my_category:<20}" if tr.my_category else " " * 20
    #     print_name = f"{tr.name:<60}"
    #     print(print_time, print_my_category, print_amt, print_name)

    totals = {}
    for tr in all_transactions:
        if tr.my_category not in totals:
            totals[tr.my_category] = 0
        totals[tr.my_category] += tr.amount

    # f"{tr.my_category:<20}"
    
    for category, total in totals.items():
        print(f"{category:<20} {total:<10.2f}")


def main():
    parser = argparse.ArgumentParser(description="My CLI tool", formatter_class=RawTextHelpFormatter)
    # parser.add_argument('--filter-by', type=str, help='filter cards', choices=MY_CARDS_VALS)

    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_update = subparsers.add_parser("update", help="Update a resource")
    parser_update.add_argument("--get-all", help="Update all transactions from beginning", action="store_true")
    parser_update.add_argument("--force", help="Replace existing transactions in DB", action="store_true")
    parser_update.add_argument('--filter-by', type=str, help='filter cards', choices=MY_CARDS_VALS)
    parser_update.set_defaults(func=do_update)


    parser_get = subparsers.add_parser("get", help="Get a resource")
    parser_get.add_argument("--category", type=str, help="Filter by category")
    parser_get.add_argument("--hide-goals", action="store_true", help="Hide goals")
    parser_get.add_argument('--filter-by', type=str, help='filter cards', choices=MY_CARDS_VALS)
    parser_get.add_argument("--show-transactions", action="store_true", default=False, help="Show individual transactions")


    date_group = parser_get.add_mutually_exclusive_group()
    # date_group.add_argument("--last-n-days", type=int, help="Get transactions from the last N days")
    date_group.add_argument("--from-to-date", nargs=2, help="Date range (FROM TO), e.g. 2025-09-01 2025-09-15")
    date_group.add_argument("--this-month", action="store_true", default=False, help="Shows from beg of month to today")
    date_group.add_argument("--last-month", action="store_true", default=False, help="Shows from exactly a month ago")
    date_group.add_argument("--last-week", action="store_true", default=False, help="Show from exactly a week ago")

    parser_get.set_defaults(func=do_get)


    parser_categorize = subparsers.add_parser("categorize", help="Categorize transactions")
    parser_categorize.add_argument("--force", action="store_true", default=False, help="Force categorize transactions even if already categorized")
    parser_categorize.add_argument('--filter-by', type=str, help='filter cards', choices=MY_CARDS_VALS)

    date_group_2 = parser_categorize.add_mutually_exclusive_group()
    date_group_2.add_argument("--from-to-date", nargs=2, help="Date range (FROM TO), e.g. 2025-09-01 2025-09-15")
    date_group_2.add_argument("--this-month", action="store_true", default=False, help="Shows from beg of month to today")
    date_group_2.add_argument("--last-month", action="store_true", default=False, help="Shows from exactly a month ago")
    date_group_2.add_argument("--last-week", action="store_true", default=False, help="Show from exactly a week ago")

    parser_categorize.set_defaults(func=do_categorize)

    parser_summary = subparsers.add_parser("summary", help="Summarize transactions")
    parser_summary.add_argument('--filter-by', type=str, help='filter cards', choices=MY_CARDS_VALS)

    date_group_3 = parser_summary.add_mutually_exclusive_group()
    date_group_3.add_argument("--from-to-date", nargs=2, help="Date range (FROM TO), e.g. 2025-09-01 2025-09-15")
    date_group_3.add_argument("--this-month", action="store_true", default=False, help="Shows from beg of month to today")
    date_group_3.add_argument("--last-month", action="store_true", default=False, help="Shows from exactly a month ago")
    date_group_3.add_argument("--last-week", action="store_true", default=False, help="Show from exactly a week ago")

    parser_summary.set_defaults(func=do_summary)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
