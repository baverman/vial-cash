from textwrap import dedent
import pytest
from cash import parse, Cash, walk_acc, collect_stats


def fromstring(data):
    data = dedent(data)
    return parse(data.splitlines())


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

    accs, curs = collect_stats(cash, ['e'])
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
