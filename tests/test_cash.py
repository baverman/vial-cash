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

