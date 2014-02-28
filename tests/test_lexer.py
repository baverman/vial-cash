from cash import parse

def test_test():
    lines = open('/home/bobrov/cash/my.cash')
    print vars(parse(lines))
