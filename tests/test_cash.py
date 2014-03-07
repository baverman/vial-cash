from cash import parse
from textwrap import dedent

def fromstring(data):
    data = dedent(data)
    return parse(data.splitlines())


def test_simple_transaction():
    cash = fromstring('''
        2014-01-01
            a:pocket
                e:food 100
                e:games 200
    ''')

    assert cash.accounts['a'].balance.USD == -300
    assert cash.accounts['e'].balance.USD == 300
    assert cash.accounts['e:food'].balance.USD == 100
    assert cash.accounts['e:games'].balance.USD == 200
    assert cash.expenses.accounts['food'].balance.USD == 100
    assert cash.expenses.accounts['games'].balance.USD == 200


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


def test_default_currency():
    cash = fromstring('''
        currency RUR
        initial a:pocket 300
        2014-01-01 a:pocket e:food 200
    ''')

    assert cash.assets.balance.USD == 0
    assert cash.assets.balance.RUR == 100
    assert cash.expenses.balance.RUR == 200


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
