from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod
import json
import os


class CardType(Enum):
    CHASEPRIME = "chase_prime"
    BILT = "bilt"
    VENMO = "venmo"


@dataclass
class MyTransaction:
    datetime: float # unix
    amount: float
    name: str
    merchant_name: str
    plaid_category: str
    plaid_subcategory: str
    account: str
    transaction_id: str
    is_categorized: bool
    my_category: str | None = None


"""

amount
date
datetime?
name
merchant_name
personal_finance_category
website?
city?
credit_card
transaction_id
is_categorized

"""