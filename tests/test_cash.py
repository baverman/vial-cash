from textwrap import dedent
from datetime import date

import pytest
from cash import (
    parse, Cash, walk_acc, collect_stats, make_cash, month_range, prev_month)


def fromstring(data, start=None, end=None):
    data = dedent(data)
    return make_cash(parse(data.splitlines()), start, end)


def test_month_range():
    start, end = month_range(date(2019, 5, 10))
    assert start == date(2019, 5, 1)
    assert end == date(2019, 6, 1)

    start, end = month_range(date(2019, 12, 10))
    assert start == date(2019, 12, 1)
    assert end == date(2020, 1, 1)

    assert prev_month(date(2019, 5, 10)) == date(2019, 4, 10)
    assert prev_month(date(2019, 1, 10)) == date(2018, 12, 10)


def test_get_account():
    cash = Cash()
    assert cash.get_account('a:boo')

    with pytest.raises(KeyError):
        assert cash.get_account('boo:foo')


def test_simple_transaction():
    cash = fromstring('''
        # some comment
        2014-01-01
            a:pocket
                e:food 100 # Grocery
                e:games 200
    ''')

    assert cash.accounts['a'].balance.USD == -300
    assert cash.accounts['e'].balance.USD == 300
    assert cash.accounts['e:food'].balance.USD == 100
    assert cash.accounts['e:games'].balance.USD == 200
    assert cash.expenses.accounts['food'].balance.USD == 100
    assert cash.expenses.accounts['games'].balance.USD == 200

    assert repr(cash.accounts['a']) == "Account(a, {'USD': -300.0})"

    a1, a2 = list(walk_acc(cash.assets))
    assert a1 is cash.assets
    assert a2 is cash.get_account('a:pocket')

    accs, curs = collect_stats(cash, ['e'], 1)
    assert 'USD' in curs


def test_liabilities_should_account_negative_amounts():
    cash = fromstring('''
        initial l:friend 100
        2014-01-01 l:friend e:restaurant 200
        2014-01-02 a:pocket l:friend 100
    ''')

    assert cash.accounts['l'].balance.USD == 200
    assert cash.accounts['a'].balance.USD == -100
    assert cash.equity.USD == -300


def test_initial_amounts():
    cash = fromstring('''
        initial a:pocket 300
        initial a:bank 100
    ''')

    assert cash.assets.balance.USD == 400
    assert cash.accounts['a:pocket'].balance.USD == 300
    assert cash.accounts['a:bank'].balance.USD == 100


def test_currency():
    cash = fromstring('''
        currency BOO
        rate FOOBOO 3
        initial a:pocket 300
        2014-01-01 a:pocket e:food 50 FOO
    ''')

    assert cash.assets.balance.BOO == 300
    assert cash.assets.balance.FOO == -50
    assert cash.expenses.balance.FOO == 50
    assert cash.total(cash.assets.balance) == 150


def test_multi_transactions():
    cash = fromstring('''
        2014-01-01 a:pocket
            e:food 200
            e:flat 100
    ''')

    assert cash.assets.balance.USD == -300
    assert cash.expenses.balance.USD == 300


def test_reversed_multi_transactions():
    cash = fromstring('''
        2014-01-01
            rev e:flat
                a:pocket 500
                l:friend 100
    ''')

    assert cash.assets.balance.USD == -500
    assert cash.expenses.balance.USD == 600
    assert cash.liabilities.balance.USD == 100
    assert cash.equity.USD == -600


def test_split():
    cash = fromstring('''
        2014-01-01
            split
                a:pocket -500
                l:friend -100
                e:flat 600
    ''')

    assert cash.assets.balance.USD == -500
    assert cash.expenses.balance.USD == 600
    assert cash.liabilities.balance.USD == 100
    assert cash.equity.USD == -600


def test_op_filter():
    cash = fromstring('''
        2019-01-01 a:pocket e:gear 1000
        2019-02-01 a:pocket e:gear 2000
    ''', date(2019, 1, 1), date(2019, 2, 1))
    assert cash.expenses.balance.USD == 1000

    cash = fromstring('''
        2019-01-01 a:pocket e:gear 1000
        2019-02-01 a:pocket e:gear 2000
    ''', None, date(2019, 2, 1))
    assert cash.expenses.balance.USD == 1000

    cash = fromstring('''
        2019-01-01 a:pocket e:gear 1000
        2019-02-01 a:pocket e:gear 2000
    ''', date(2019, 2, 1))
    assert cash.expenses.balance.USD == 2000
