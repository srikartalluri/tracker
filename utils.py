import plaid
from plaid.api import plaid_api
import os
import plaid.model
import plaid.model.transaction
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from dotenv import load_dotenv
load_dotenv()
from datetime import date, timedelta, datetime
from mytypes import MyTransaction, CardType
import json
from dataclasses import asdict
from pathlib import Path

import tinydb
from tinydb import TinyDB, Query


# DB_PATH = "/Desktop/workspace/plaid_app/db/transactions_db.json"
# LAST_SYNCS_PATH = "/Desktop/workspace/plaid_app/db/last_syncs.json"
base = Path(__file__).parent  # directory where your script lives
DB_PATH = base / "db" / "transactions_db.json"
LAST_SYNCS_PATH = base / "db" / "last_syncs.json"


def get_access_token(card_type: CardType) -> str:
    print(f"Getting access token for {card_type.name}")
    return os.getenv(f"PLAID_{card_type.name}_ACCESS_TOKEN")

def get_cursor(card_type: CardType) -> str | None:
    with open(LAST_SYNCS_PATH, "r") as f:
        data = json.load(f)
        return data.get(card_type.name.lower())

def update_cursor(card_type: CardType, new_cursor: str | None):
    with open(LAST_SYNCS_PATH, "r") as f:
        data = json.load(f)
    data[card_type.name.lower()] = new_cursor
    with open(LAST_SYNCS_PATH, "w") as f:
        json.dump(data, f, indent=2)

def convert_to_mytransaction(plaid_transaction: plaid.model.transaction.Transaction, card: CardType) -> MyTransaction:
    date_time = None
    if plaid_transaction["datetime"] is not None:
        date_time = plaid_transaction["datetime"]
    else:
        d = plaid_transaction["date"]
        date_time = datetime.combine(d, datetime.min.time())

    date_time = date_time.timestamp()

    my_transaction = MyTransaction(
        datetime=date_time,
        amount=plaid_transaction["amount"],
        name=plaid_transaction["name"],
        merchant_name=plaid_transaction["merchant_name"],
        plaid_category=plaid_transaction["personal_finance_category"]["primary"],
        plaid_subcategory=plaid_transaction["personal_finance_category"]["detailed"],
        account=card.name,
        transaction_id=plaid_transaction["transaction_id"],
        is_categorized=False,
        my_category=None
    )

    return my_transaction


def get_transactions_list_from_plaid(card: CardType, get_all = False) -> list[MyTransaction]:
    access_token = get_access_token(card)
    if access_token is None:
        raise ValueError(f"Access token for {card} is not set in environment variables.")
    
    if get_all:
        request = TransactionsSyncRequest(
            access_token=access_token,
            count=500
        )
    else:
        request = TransactionsSyncRequest(
            access_token=access_token,
            count=500,
            cursor=get_cursor(card)
        )

    client = plaid_api.PlaidApi(plaid.ApiClient(plaid.Configuration(
        host=plaid.Environment.Production,
        api_key={
            'clientId': os.getenv("PLAID_CLIENT_ID"),
            'secret': os.getenv("PLAID_SECRET")
        }
    )))
    response = client.transactions_sync(request)
    transactions = response['added']
    new_cursor = response['next_cursor']
    update_cursor(card, new_cursor)
    
    my_transactions = [convert_to_mytransaction(tr, card) for tr in transactions]

    if response["has_more"]:
        my_transactions.extend(get_transactions_list_from_plaid(card, get_all=False))

    return my_transactions


def update_db_single(db, one_transaction: MyTransaction, replace_if_exists = False) -> bool:
    Transaction = Query()

    existing = db.search(Transaction.transaction_id == one_transaction.transaction_id)
    if len(existing) == 0:
        db.insert(asdict(one_transaction))
        return True
    else:
        if replace_if_exists:
            db.update(asdict(one_transaction), Transaction.transaction_id == one_transaction.transaction_id)
            return True
        return False

def update_db_from_list(new_transactions: list[MyTransaction], replace_if_exists = False):
    db = TinyDB(DB_PATH)
    count = 0
    skipped = 0
    for tr in new_transactions:
        if update_db_single(db, tr, replace_if_exists=replace_if_exists):
            count += 1
        else:
            skipped += 1
    db.close()
    return count, skipped

def update_db_from_plaid(card: CardType, get_all = False, replace_if_exists = False):
    new_transactions = get_transactions_list_from_plaid(card, get_all)
    count, skipped = update_db_from_list(new_transactions, replace_if_exists=replace_if_exists)
    print(f"Inserted {count} new transactions from {card.name} into DB.")
    print(f"Skipped {skipped} existing transactions for {card.name}.")



# Analytics stuff

def get_transactions_between_dates(start_date: date, end_date: date, card: CardType, get_only_uncategorized: bool = False) -> list[MyTransaction]:
    db = TinyDB(DB_PATH)
    Transaction = Query()
    start_timestamp = datetime.combine(start_date, datetime.min.time()).timestamp()
    end_timestamp = datetime.combine(end_date + timedelta(days=1), datetime.min.time()).timestamp() - 1
    

    if get_only_uncategorized:
        results = db.search((Transaction.datetime >= start_timestamp) & (Transaction.datetime <= end_timestamp) & (Transaction.account == card.name) & (Transaction.my_category == None))
    else:
        results = db.search((Transaction.datetime >= start_timestamp) & (Transaction.datetime <= end_timestamp) & (Transaction.account == card.name))
    db.close()
    return [MyTransaction(**res) for res in results]

