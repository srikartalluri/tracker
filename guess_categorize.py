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
from typing import Callable, Optional


MY_CARDS_VALS = [CardType.CHASEPRIME.value, CardType.BILT.value, CardType.VENMO.value]

CARD_TYPE_MAP = {
    CardType.CHASEPRIME.value: CardType.CHASEPRIME,
    CardType.BILT.value: CardType.BILT,
    CardType.VENMO.value: CardType.VENMO,
}


import json

# Open and load the JSON file
with open("./db/categories.json", "r") as file:
    categories = json.load(file)

def contains_rule(target: str, category: str) -> Callable[[str], Optional[str]]:
    target = target.lower()
    category = category.lower()

    return lambda name: category if target in name.lower() else None

def regex_rule(pattern: str, category: str) -> Callable[[str], Optional[str]]:
    import re
    pattern = re.compile(pattern, re.IGNORECASE)
    category = category.lower()

    return lambda name: category if pattern.search(name) else None

def equal_rule(target: str, category: str) -> Callable[[str], Optional[str]]:
    target = target.lower()
    category = category.lower()

    return lambda name: category if name.lower() == target else None

RULES = []

with open("./db/my_rules.json", "r") as file:
    my_rules = json.load(file)
    for rule in my_rules["contains_rules"]:
        RULES.append(contains_rule(rule["target"], rule["category"]))




def guess_category(name: str, merchant_name: str) -> str | None:
    name = name.lower()

    for rule_fn in RULES:
        category = rule_fn(name)
        if category:
            return category
    return None