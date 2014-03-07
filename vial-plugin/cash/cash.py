#!/usr/bin/env python2
from datetime import datetime, date
from collections import namedtuple, defaultdict, OrderedDict

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
SPLIT    = 'split'
REV      = 'rev'
KEYWORDS = {r:r for r in (CURRENCY, RATE, INITIAL, SPLIT, REV)}

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
                    continue

                if '-' in part:
                    try:
                        yield Token(DATE, datetime.strptime(part, DATEFMT).date(), ln)
                        continue
                    except ValueError: pass

                try:
                    value = float(part)
                except ValueError:
                    yield Token(ID, part, ln)
                else:
                    yield Token(NUMBER, value, ln)

        yield Token(LEND, None, ln)


class TokenFeed(object):
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
            raise Exception('line {}: {} not in {}'.format(
                token.line, token.id, ids))

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

    def indent(self, func):
        if self.skipif(LEND):
            indent = self.peek().value
            while self.skipif(INDENT, indent):
                func()
        else:
            func()


def parse_rate(tokens, cash):
    @tokens.indent
    def parse():
        cur = tokens.popany(ID).value
        multiplier = tokens.popany(NUMBER).value
        cash.rates[cur] = multiplier
        tokens.popany(LEND)


def parse_initial(tokens, cash):
    @tokens.indent
    def parse():
        account = tokens.popany(CID).value
        amount = tokens.popany(NUMBER).value
        currency = tokens.get(ID)
        comment = tokens.get(COMMENT)
        cash.add_operation(INITDATE, None, account, amount, currency, comment)
        tokens.popany(LEND)


def parse_date(tokens, cash, dt):
    @tokens.indent
    def parse_from():
        if tokens.skipif(SPLIT):
            @tokens.indent
            def parse():
                acc = tokens.popany(CID).value

                @tokens.indent
                def parse_op():
                    amount = tokens.popany(NUMBER).value
                    currency = tokens.get(ID)
                    comment = tokens.get(COMMENT)
                    cash.process_account(acc, amount, currency)
                    tokens.popany(LEND)
        else:
            reverse = tokens.skipif(REV)
            acc1 = tokens.popany(CID).value

            @tokens.indent
            def parse_to():
                acc2 = tokens.popany(CID).value

                @tokens.indent
                def parse_op():
                    amount = tokens.popany(NUMBER).value
                    currency = tokens.get(ID)
                    comment = tokens.get(COMMENT)
                    if reverse:
                        cash.add_operation(dt, acc2, acc1, amount, currency, comment)
                    else:
                        cash.add_operation(dt, acc1, acc2, amount, currency, comment)

                    tokens.popany(LEND)


def parse_root(tokens, cash):
    token = tokens.popany(RATE, CURRENCY, INITIAL, DATE, COMMENT)
    if token.id == CURRENCY:
        cash.currency = tokens.popany(ID).value
        tokens.popany(LEND)
    elif token.id == RATE:
        parse_rate(tokens, cash)
    elif token.id == INITIAL:
        parse_initial(tokens, cash)
    elif token.id == DATE:
        parse_date(tokens, cash, token.value)
    elif token.id == COMMENT:
        tokens.popany(LEND)


def parse(lines):
    cash = Cash()
    tokens = TokenFeed(lexer(lines))
    try:
        while True:
            parse_root(tokens, cash)
    except StopIteration:
        pass

    return cash


class pddict(defaultdict):
    __getattr__ = defaultdict.__getitem__


class pdict(dict):
    __getattr__ = dict.__getitem__


class Account(object):
    def __init__(self, qname, title, reverse=None, parent=None):
        self.parent = parent
        self.qname = qname
        self.title = title
        self.balance = pddict(float)
        self.reverse = reverse or 1.0
        self.accounts = {}
        if parent:
            self.level = parent.level + 1
        else:
            self.level = 0

    def add(self, amount, currency, initial=False):
        if not initial:
            amount *= self.reverse
        self.balance[currency] += amount

    def __repr__(self):
        return '{}: {}'.format(self.qname, dict(self.balance))


class Cash(object):
    def __init__(self, currency=None):
        self.assets = Account('a', 'assets')
        self.expenses = Account('e', 'expenses')
        self.liabilities = Account('l', 'liabilities', -1.0)
        self.income = Account('i', 'income', -1.0)
        self.accounts = {r.qname: r for r in (self.assets, self.expenses,
            self.liabilities, self.income)}

        self.currency = currency or 'USD'
        self.rates = {}

    def get_account(self, qname):
        try:
            return self.accounts[qname]
        except KeyError:
            pass

        pqname, _, title = qname.rpartition(':')
        if not pqname:
            raise KeyError(qname)

        parent = self.get_account(pqname)
        account = self.accounts[qname] = Account(qname,
            title, parent.reverse, parent)

        parent.accounts[title] = account
        return account

    def convert_amount(self, from_currency, to_currency, amount):
        if from_currency == to_currency:
            return amount

        return amount * self.rates[from_currency + to_currency]

    def process_account(self, name, amount, currency, initial=False):
        currency = currency or self.currency
        account = self.get_account(name)
        while account:
            account.add(amount, currency, initial)
            account = account.parent

    def add_operation(self, date, from_acc, to_acc, amount, currency, comment):
        if from_acc:
            self.process_account(from_acc, -amount, currency)

        self.process_account(to_acc, amount, currency, not from_acc)

    @property
    def equity(self):
        curs = set(self.assets.balance)
        curs.update(self.liabilities.balance)
        return pdict({r: self.assets.balance[r] - self.liabilities.balance[r] for r in curs})

    def total(self, balance):
        return sum(self.convert_amount(cur, self.currency, amount)
            for cur, amount in balance.iteritems())


def walk_acc(acc):
    yield acc
    for child in sorted(acc.accounts.itervalues(), key=lambda r: r.title):
        for a in walk_acc(child):
            yield a


def collect_stats(cash, accounts):
    currencies = OrderedDict()
    currencies[cash.currency] = True
    non_zero_accounts = []

    for acc_name in accounts:
        for acc in walk_acc(cash.accounts[acc_name]):
            if any(acc.balance.itervalues()):
                non_zero_accounts.append(acc)
                for cur, amount in acc.balance.iteritems():
                    if amount:
                        currencies[cur] = True

    return non_zero_accounts, currencies


def get_format(accounts, curs, indent=2):
    max_width = max(indent * r.level + len(r.title) for r in accounts)
    titlefmt = '{{0:<{}}}'.format(max_width)
    amountfmt = '  '.join('{{1[{}]:10.2f}}'.format(r) for r in curs)
    headerfmt = '  '.join('{{{}:>10}}'.format(i) for i, r in enumerate(curs, 1))
    fmt = '{}  {}'.format(titlefmt, amountfmt)
    hfmt = '{}  {}'.format(titlefmt, headerfmt)
    return fmt, hfmt


def report(cash):
    nzaccounts, curs = collect_stats(cash, ['a', 'l'])
    fmt, hfmt = get_format(nzaccounts, curs)
    first = True
    print hfmt.format('', *curs)
    for acc in nzaccounts:
        if not first and acc.level == 0:
            print
        first = False
        print fmt.format('  ' * acc.level + acc.title, acc.balance)

    print
    equity = cash.equity
    print fmt.format('equity', equity), ' {:10.2f}'.format(cash.total(equity))


if __name__ == '__main__':
    import sys
    cash = parse(open(sys.argv[1]))
    report(cash)
