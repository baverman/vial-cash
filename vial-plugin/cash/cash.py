from datetime import datetime, date
from collections import namedtuple

LEND    = 'lend'
INDENT  = 'indent'
DATE    = 'date'
COMMENT = 'comment'
NUMBER  = 'number'
ID      = 'id'
CID     = 'cid'

CURRENCY = 'currency'
RATE     = 'rate'
INITIAL  = 'initial'
AS       = 'as'
KEYWORDS = {r:r for r in (CURRENCY, RATE, INITIAL, AS)}

DATEFMT = '%Y-%m-%d'
INITDATE = date(1983, 6, 11)

Token = namedtuple('Token', 'id value line')

def lexer(lines):
    for ln, line in enumerate(lines, 1):
        sline = line.lstrip()
        if not sline:
            continue

        iwidth = len(line) - len(sline)
        if iwidth:
            yield Token(INDENT, line[:iwidth], ln)

        parts = line.strip().split()
        while parts:
            part = parts.pop(0)
            if part == '#':
                yield Token(COMMENT, ' '.join(parts), ln)
                parts = None
            elif part in KEYWORDS:
                yield Token(KEYWORDS[part], part, ln)
            else:
                if ':' in part:
                    yield Token(CID, part, ln)
                elif '-' in part:
                    yield Token(DATE, datetime.strptime(part, DATEFMT).date(), ln)
                else:
                    try:
                        value = float(part)
                    except ValueError:
                        yield Token(ID, part, ln)
                    else:
                        yield Token(NUMBER, value, ln)

        yield Token(LEND, None, ln)


class TokenGenerator(object):
    def __init__(self, lexer):
        self.lexer = lexer
        self.item = None

    def pop(self):
        if self.item:
            item = self.item
            self.item = None
            return item

        return next(self.lexer)

    def peek(self):
        item = self.pop()
        self.item = item
        return item

    def popany(self, *ids):
        token = self.pop()
        if token.id not in ids:
            raise Exception('line {}: {} not in {}'.format(token.line, token.id, ids))

        return token

    def nextis(self, id):
        token = self.peek()
        return token.id == id

    def skipif(self, id, value=None):
        token = self.pop()
        if token.id == id and (value is None or token.value == value):
            return True

        self.item = token
        return False

    def get(self, id):
        if self.nextis(id):
            return self.pop().value


def parse_currency(tokens, cash):
    cash.currency = tokens.popany(ID).value
    tokens.popany(LEND)


def parse_rate(tokens, cash):
    cur = tokens.popany(ID)[1]
    multiplier = tokens.popany(NUMBER)[1]
    cash.rates[cur] = multiplier
    tokens.popany(LEND)


def parse_rates(tokens, cash):
    if tokens.skipif(LEND):
        while tokens.skipif(INDENT):
            parse_rate(tokens, cash)
    else:
        parse_rate(tokens, cash)


def parse_initial(tokens, cash):
    account = tokens.popany(CID)[1]
    amount = tokens.popany(NUMBER)[1]
    currency = tokens.get(ID)
    comment = tokens.get(COMMENT)
    cash.add_operation(INITDATE, None, account, amount, currency, comment)
    tokens.popany(LEND)


def parse_initials(tokens, cash):
    if tokens.skipif(LEND):
        while tokens.skipif(INDENT):
            parse_initial(tokens, cash)
    else:
        parse_initial(tokens, cash)


def parse_op_amount(tokens, cash, dt, account_from, account_to):
    amount = tokens.popany(NUMBER)[1]
    currency = tokens.get(ID)
    comment = tokens.get(COMMENT)
    cash.add_operation(dt, account_from, account_to, amount, currency, comment)
    tokens.popany(LEND)


def parse_op_tail(tokens, cash, dt, account_from):
    account_to = tokens.popany(CID)[1]
    if tokens.skipif(LEND):
        indent = tokens.peek().value
        while tokens.skipif(INDENT, indent):
            parse_op_amount(tokens, cash, dt, account_from, account_to)
    else:
        parse_op_amount(tokens, cash, dt, account_from, account_to)


def parse_op(tokens, cash, dt):
    account_from = tokens.popany(CID)[1]
    if tokens.skipif(LEND):
        indent = tokens.peek().value
        while tokens.skipif(INDENT, indent):
            parse_op_tail(tokens, cash, dt, account_from)
    else:
        parse_op_tail(tokens, cash, dt, account_from)


def parse_date(tokens, cash, dt):
    if tokens.skipif(LEND):
        while tokens.skipif(INDENT):
            parse_op(tokens, cash, dt)
    else:
        parse_op(tokens, cash, dt)


def parse_root(tokens, cash):
    token = tokens.popany(RATE, CURRENCY, INITIAL, DATE, COMMENT)
    if token.id == CURRENCY:
        parse_currency(tokens, cash)
    elif token.id == RATE:
        parse_rates(tokens, cash)
    elif token.id == INITIAL:
        parse_initials(tokens, cash)
    elif token.id == DATE:
        parse_date(tokens, cash, token.value)
    elif token.id == COMMENT:
        tokens.popany(LEND)


def parse(lines):
    cash = Cash()
    tokens = TokenGenerator(lexer(lines))
    try:
        while True:
            parse_root(tokens, cash)
    except StopIteration:
        pass

    return cash


class Account(object):
    def __init__(self, cash, name, currency):
        self.cash = cash
        self.name = name
        self.currency = currency
        self.balance = 0

    def add(self, amount, currency):
        self.balance += self.cash.convert_amount(currency, self.currency, amount)

    def __repr__(self):
        return '{} ({}): {}'.format(self.name, self.currency, self.balance)


class Cash(object):
    def __init__(self):
        self.accounts = {}
        self.operations = []
        self.currency = 'USD'
        self.rates = {}

    def get_account(self, name, currency):
        try:
            return self.accounts[name]
        except KeyError:
            pass

        account = self.accounts[name] = Account(self, name, currency or self.currency)
        return account

    def convert_amount(self, from_currency, to_currency, amount):
        if from_currency == to_currency:
            return amount

        return amount * self.rates[from_currency + to_currency]

    def process_account(self, name, amount, currency):
        acur = currency = currency or self.currency
        while name:
            self.get_account(name, acur).add(amount, currency)
            name = name.rpartition(':')[0]
            acur = self.currency

    def add_operation(self, date, from_acc, to_acc, amount, currency, comment):
        if from_acc:
            self.process_account(from_acc, -amount, currency)

        self.process_account(to_acc, amount, currency)


if __name__ == '__main__':
    pass
