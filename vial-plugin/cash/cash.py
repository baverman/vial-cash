#!/usr/bin/env python
from __future__ import print_function

import argparse
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
Op = namedtuple('Op', 'initial dt account amount currency comment')


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
        if token.id not in ids:  # pragma: no cover
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


def parse_rate(tokens, config):
    @tokens.indent
    def parse():
        cur = tokens.popany(ID).value
        multiplier = tokens.popany(NUMBER).value
        config['rates'][cur] = multiplier
        tokens.popany(LEND)


def parse_initial(tokens, config):
    @tokens.indent
    def parse():
        account = tokens.popany(CID).value
        amount = tokens.popany(NUMBER).value
        currency = tokens.get(ID)
        comment = tokens.get(COMMENT)
        config['ops'].append(Op(True, INITDATE, account, amount, currency, comment))
        tokens.popany(LEND)


def parse_date(tokens, config, dt):
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
                    config['ops'].append(Op(False, dt, acc, amount, currency, comment))
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
                        amount = -amount
                    config['ops'].append(Op(False, dt, acc1, -amount, currency, comment))
                    config['ops'].append(Op(False, dt, acc2, amount, currency, comment))
                    tokens.popany(LEND)


def parse_root(tokens, config):
    token = tokens.popany(RATE, CURRENCY, INITIAL, DATE, COMMENT)
    if token.id == CURRENCY:
        config['currency'] = tokens.popany(ID).value
        tokens.popany(LEND)
    elif token.id == RATE:
        parse_rate(tokens, config)
    elif token.id == INITIAL:
        parse_initial(tokens, config)
    elif token.id == DATE:
        parse_date(tokens, config, token.value)
    elif token.id == COMMENT:
        tokens.popany(LEND)


def parse(lines):
    config = {
        'currency': None,
        'rates': {},
        'ops': [],
    }
    tokens = TokenFeed(lexer(lines))
    try:
        while True:
            parse_root(tokens, config)
    except StopIteration:
        pass

    return config


def make_cash(config, start=None, end=None):
    cash = Cash(config['currency'])
    cash.rates.update(config['rates'])
    cash.apply_operations(filter_ops(config['ops'], start, end))
    return cash


def filter_ops(ops, start, end):
    return (it for it in ops if (not start or it.dt >= start)
            and (not end or it.dt < end))


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
        return 'Account({}, {})'.format(self.qname, dict(self.balance))


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

    def apply_operations(self, ops):
        for op in ops:
            self.process_account(op.account, op.amount, op.currency, op.initial)

    @property
    def equity(self):
        curs = set(self.assets.balance)
        curs.update(self.liabilities.balance)
        return pdict({r: self.assets.balance[r] - self.liabilities.balance[r] for r in curs})

    def total(self, balance):
        return sum(self.convert_amount(cur, self.currency, amount)
            for cur, amount in balance.items())


def walk_acc(acc, max_level=None):
    yield acc
    if max_level is not None and acc.level >= max_level:
        return
    for child in sorted(acc.accounts.values(), key=lambda r: r.title):
        for a in walk_acc(child, max_level):
            yield a


def collect_stats(cash, accounts, max_level=None):
    currencies = OrderedDict()
    currencies[cash.currency] = True
    non_zero_accounts = []

    for acc_name in accounts:
        for acc in walk_acc(cash.accounts[acc_name], max_level):
            if any(acc.balance.values()):
                non_zero_accounts.append(acc)
                for cur, amount in acc.balance.items():
                    if amount:
                        currencies[cur] = True

    return non_zero_accounts, currencies


def next_month(dt):
    yd, month = divmod(dt.month, 12)
    return dt.replace(year=dt.year+yd, month=month+1)


def prev_month(dt):
    yd, month = divmod(dt.month - 2, 12)
    return dt.replace(year=dt.year+yd, month=month+1)


def month_range(dt):
    start = dt.replace(day=1)
    end = next_month(start)
    return start, end


def get_format(accounts, curs, indent=2):  # pragma: no cover
    max_width = max(indent * r.level + len(r.title) for r in accounts)
    titlefmt = '{{0:<{}}}'.format(max_width)
    amountfmt = '  '.join('{{1[{}]:10.2f}}'.format(r) for r in curs)
    headerfmt = '  '.join('{{{}:>10}}'.format(i) for i, r in enumerate(curs, 1))
    fmt = '{}  {}'.format(titlefmt, amountfmt)
    hfmt = '{}  {}'.format(titlefmt, headerfmt)
    return fmt, hfmt


def report(cash, accs, with_equity=False, max_level=None):  # pragma: no cover
    nzaccounts, curs = collect_stats(cash, accs, max_level=max_level)

    if not nzaccounts:
        print('No data')
        return

    fmt, hfmt = get_format(nzaccounts, curs)
    first = True
    print(hfmt.format('', *curs))
    for acc in nzaccounts:
        if not first and acc.level == 0:
            print()
        first = False
        print(fmt.format('  ' * acc.level + acc.title, acc.balance))

    if with_equity:
        print()
        equity = cash.equity
        print(fmt.format('equity', equity), ' {:10.2f}'.format(cash.total(equity)))


def do_balance_report(args):  # pragma: no cover
    cash = make_cash(parse(args.file))
    report(cash, ['a', 'l'], True, max_level=args.level)


def do_month_report(args):  # pragma: no cover
    config = parse(args.file)
    if args.month == 'current':
        start, end = month_range(date.today())
    elif args.month == 'prev':
        end, _ = month_range(date.today())
        start = prev_month(end)

    cash = make_cash(config, start, end)
    report(cash, ['e', 'i'], max_level=args.level)


def main():  # pragma: no cover
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    p = subparsers.add_parser('balance', help='show balance report')
    p.add_argument('--level', '-l', type=int)
    p.add_argument('file', type=argparse.FileType())
    p.set_defaults(call=do_balance_report)

    p = subparsers.add_parser('month', help='show month report')
    p.add_argument('--level', '-l', type=int)
    p.add_argument('--month', '-m', default='current')
    p.add_argument('file', type=argparse.FileType())
    p.set_defaults(call=do_month_report)

    args = parser.parse_args()
    args.call(args)


if __name__ == '__main__':  # pragma: no cover
    main()
