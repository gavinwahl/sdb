import os
import random
try:
    from StringIO import StringIO
    BytesIO = StringIO
except ImportError:
    from io import StringIO, BytesIO
from unittest import TestCase
from tempfile import NamedTemporaryFile

import pytest

from sdb.passwords import *

def random_str(n=1000):
    return os.urandom(random.randint(0, n))

def random_tuple(len):
    return tuple(random_str() for i in range(len))

def test_encode_decode():
    for i in range(25):
        records = [random_tuple(4) for i in range(10)]
        assert records == decode(encode(records))

    assert [] == decode(encode([]))

def test_clipboard():
    restore = get_clipboard()
    try:
        x = b'asdf'
        set_clipboard(x)
        assert get_clipboard() == x

        x = b'foobar'
        set_clipboard(x)
        assert get_clipboard() == x

        copy_to_clipboard('fafa', .1)
        # clipboard should be unchanged by the time copy_to_clipboard returns
        assert get_clipboard() == x
    finally:
        # try to not clobber the system clipboard during testing
        set_clipboard(restore)

def test_clipboard_no_x():
    import os
    d = os.environ['DISPLAY']
    try:
        del os.environ['DISPLAY']
        with pytest.raises(ClipboardException):
            set_clipboard('a')
    finally:
        os.environ['DISPLAY'] = d


def test_gen_password():
    pw = []
    for i in range(100):
        pw.append(gen_password())

    # no duplicates
    assert len(set(pw)) == len(pw)

    for i in range(25):
        assert len(gen_password(length=i)) == i

    for i in range(25):
        assert 'a' in gen_password_require('a')
        assert 'b' in gen_password_require('ab')

def test_match():
    assert match('a', 'a')
    assert match('', 'a')
    assert match('', '')
    assert match('ab', 'acba')
    assert not match('a', '')
    assert not match('a', 'bb')
    assert match('foo', 'afoaaaao')
    assert not match('foooo', 'afoaaaao')
    assert not match('asdf', 'asdieieieieie')
    assert not match('asdf', 'ffffsdf')
    assert match('asdf', 'ffaffsdf')

def test_match_scores():
    assert match('apple', 'apple') > match('apple', 'fafpfpfpflflfe')
    assert match('apple', 'alpple') > match('apple', 'fafpfpfpflflfe')
    assert match('apple', 'fapple') > match('apple', 'ffapple')


def test_search():
    records = [
            ('google.com', 'username', 'password', 'lorem ipsum dolor sit amet'),
            ('github.com', 'githubuser', 'password', 'social code'),
            ('foo.com', 'afaf', 'password', ''),
            ]

    assert search('google', records) == [records[0]]
    assert search('github', records) == [records[1]]
    assert search('foo', records) == [records[2]]

    assert search('goo', records) == [records[0], records[1]]
    assert search('git', records) == [records[1], records[0]]
    assert len(search('o', records)) == 3

def test_disambiguate():
    records = [
            ('google.com', 'username', 'password', 'lorem ipsum dolor sit amet'),
            ('github.com', 'githubuser', 'password', 'social code'),
            ]

    assert disambiguate(records) == [('google.com'), ('github.com')]

    records = [
            ('google.com', 'username', 'password', 'lorem ipsum dolor sit amet'),
            ('google.com', 'differentuser', 'password', 'social code'),
            ]

    assert disambiguate(records) == [('google.com', 'username'), ('google.com', 'differentuser')]

    records = [
            ('google.com', 'username', 'password', 'lorem ipsum dolor sit amet'),
            ('google.com', 'username', 'password', 'social code'),
            ]

    assert disambiguate(records) == [('google.com', 'username', 'lorem ipsum dolor sit amet'), ('google.com', 'username', 'social code')]

    records = [
            ('google.com', 'username', 'password', 'lorem'),
            ('google.com', 'username', 'password', 'lorem'),
            ]
    # this is dubious. should it be an error instead?
    assert disambiguate(records) == records


def test_dencrypt():
    for i in range(100):
        key = gen_password()
        data = random_str(10000)
        assert data == decrypt(key, encrypt(key, data))

    encrypted = encrypt('foo', b'asdfasdf')
    with pytest.raises(IncorrectPasswordException):
        decrypt('fo', encrypted)

    encrypted = encrypt('foo', b'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Morbi sollicitudin pharetra elit sed mollis. Proin velit nibh, laoreet consequat fringilla vitae, interdum ac dui. Nulla pretium sollicitudin enim.')
    encrypted = encrypted[:100] + encrypted[101:]
    with pytest.raises(FileCorruptionException):
        decrypt('foo', encrypted)

    with pytest.raises(GPGException):
        for i in range(100):
                p = gen_password()
                d = random_str()
                print((repr(decrypt(p, d)), repr(p), repr(d)))

def test_atomic_replace():
    f = NamedTemporaryFile(delete=False)
    filename = f.name
    f.write(b'first')

    with open(filename) as f:
        assert f.read() == 'first'

    with atomic_replace(filename) as f:
        assert os.path.exists(get_tmp_file(filename))
        f.write(b'second')

    with open(filename, 'rb') as f:
        assert f.read() == b'second'

    with open(get_backup_file(filename), 'rb') as f:
        assert f.read() == b'first'

    with atomic_replace(filename) as f:
        assert os.path.exists(get_tmp_file(filename))
        f.write(b'second')

    # don't overwrite backup when no changes made
    with open(get_backup_file(filename), 'rb') as f:
        assert f.read() == b'first'

    assert not os.path.exists(get_tmp_file(filename))

    with pytest.raises(Exception):
        with atomic_replace(filename) as f:
            f.write(b'third')
            f.close()
            raise Exception

    with open(filename, 'rb') as f:
        assert f.read() == b'second'
    assert not os.path.exists(get_tmp_file(filename))

    class ItWorkedButPanic(Exception):
        pass

    with pytest.raises(ItWorkedButPanic):
        with atomic_replace(filename) as f:
            with pytest.raises(OSError):
                with atomic_replace(filename) as f:
                    # must not be able to lock the file twice
                    assert False
            raise ItWorkedButPanic

    with pytest.raises(Exception):
        with atomic_replace(filename) as f:
            # such an easy mistake to make could result in blanking the file.
            # make sure it's caught instead
            pass
    with open(filename) as f:
        assert f.read() == 'second'

    assert not os.path.exists(get_tmp_file(filename))
    os.unlink(filename)

    with atomic_replace(filename) as f:
        f.write(b'foo')
    with open(filename, 'rb') as f:
        assert f.read() == b'foo'
    os.unlink(filename)


class Empty(object):
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestInteractive(TestCase):
    def setUp(self):
        self.filename = NamedTemporaryFile(delete=False).name
        os.unlink(self.filename)
        self.args = Empty(file=self.filename)

    def tearDown(self):
        try:
            os.unlink(self.filename)
        except OSError:
            pass

    def test_add(self):
        output = StringIO()
        input = StringIO("google.com\nusername\n\nsome notes\n")
        session = InteractiveSession(self.args, input=input, output=output, password='asdf')
        new_record = session.get_record()

        assert new_record[0] == 'google.com'
        assert new_record[1] == 'username'
        assert len(new_record[2]) > 5
        assert new_record[3] == 'some notes'

        output = StringIO()
        input = StringIO("asdf\na password\nomgwtfbbq\n")
        session = InteractiveSession(self.args, input=input, output=output, password='asdf')
        new_record = session.get_record(domain='yahoo.com')
        assert new_record == ('yahoo.com', 'asdf', 'a password', 'omgwtfbbq')

    def test_edit(self):
        output = StringIO()
        input = StringIO("\n" * 12)
        session = InteractiveSession(self.args, input=input, output=output, password='asdf')
        record = ('google.com', 'foo', 'foobar', 'notes')
        assert session.edit_record(record) == record

        input = StringIO("gmail.com\n\n\n\n")
        session = InteractiveSession(self.args, input=input, output=output, password='asdf')
        record = ('google.com', 'foo', 'foobar', 'notes')
        assert session.edit_record(record) == (
                'gmail.com', 'foo', 'foobar', 'notes'
                )

        input = StringIO("\n\ng\n\n")
        session = InteractiveSession(self.args, input=input, output=output, password='asdf')
        record = ('google.com', 'foo', 'foobar', 'notes')
        new_record = session.edit_record(record)
        assert new_record[0] == record[0]
        assert new_record[1] == record[1]
        assert new_record[2] != record[2]
        assert new_record[3] == record[3]

    def add_a_password(self, domain, username, password, notes):
        output = StringIO()
        input = StringIO('\n'.join((username, password, notes)))
        self.args.domain = domain
        session = InteractiveSession(self.args, input=input, output=output, password='asdf')
        session.add_action()

    def get_a_password(self, domain):
        output = StringIO()
        input = StringIO()
        self.args.domain = domain
        session = InteractiveSession(self.args, input=input, output=output, password='asdf')
        return session.show_action(clipboard=False), output.getvalue()

    def test_add_action(self):
        self.add_a_password('domain.com', 'username', 'password', '')
        self.add_a_password('other.com', 'otheruse', '', 'notas')

        pw, output = self.get_a_password('domain.com')
        assert pw == 'password'
        assert output == 'username@domain.com\n'

        pw, output = self.get_a_password('other')
        assert len(pw) > 5
        assert pw != 'password'
        assert output == 'otheruse@other.com: notas\n'

    def test_edit_action(self):
        self.add_a_password('domain.com', 'username', 'password', '')
        self.add_a_password('other.com', 'otheruse', 'abc', 'notas')

        output = StringIO()
        input = StringIO("\notheruser\n\n")
        self.args.domain = 'otherts'
        session = InteractiveSession(self.args, input=input, output=output, password='asdf')
        session.edit_action()

        pw, output = self.get_a_password('other')
        assert pw == 'abc'
        assert output == 'otheruser@other.com: notas\n'

        pw, output = self.get_a_password('domain.com')
        assert pw == 'password'
        assert output == 'username@domain.com\n'

        output = StringIO()
        input = StringIO("newdomain\nnewuser\nnewpassword\n")
        self.args.domain = 'otheruser'
        session = InteractiveSession(self.args, input=input, output=output, password='asdf')
        session.edit_action()

        pw, output = self.get_a_password('new')
        assert pw == 'newpassword'
        assert output == 'newuser@newdomain: notas\n'

        pw, output = self.get_a_password('domain.com')
        assert pw == 'password'
        assert output == 'username@domain.com\n'

    def test_delete_action(self):
        self.add_a_password('domain.com', 'usernamet', 'password', '')
        self.add_a_password('other.com', 'otheruse', 'abc', 'notas')
        self.add_a_password('unrelated.com', 'aaa', '', 'notes')

        output = StringIO()
        input = StringIO('0\n')
        self.args.domain = 'o'
        session = InteractiveSession(self.args, input=input, output=output, password='asdf')
        session.delete_action()

        # confirm
        pw, output = self.get_a_password('other')
        assert pw == 'abc'
        assert output == 'otheruse@other.com: notas\n'

        pw, output = self.get_a_password('domain.com')
        assert pw == 'password'
        assert output == 'usernamet@domain.com\n'

        output = StringIO()
        input = StringIO('0\ny\n')
        self.args.domain = 'ot'
        session = InteractiveSession(self.args, input=input, output=output, password='asdf')
        session.delete_action()

        print(output.getvalue())
        with pytest.raises(Exception):
            pw, output = self.get_a_password('other')
            print(pw, output)

        pw, output = self.get_a_password('domain.com')
        assert pw == 'password'
        assert output == 'usernamet@domain.com\n'

        pw, output = self.get_a_password('unrel')
        assert output == 'aaa@unrelated.com: notes\n'

    def test_raw(self):
        records = [
            ('domain.com', 'usernamet', 'password', ''),
            ('other.com', 'otheruse', 'abc', 'notas'),
            ('unrelated.com', 'aaa', 'foobar', 'notes'),
        ]
        for r in records:
            self.add_a_password(*r)

        input = StringIO()
        output = BytesIO()
        session = InteractiveSession(self.args, input=input, output=output, password='asdf')
        session.raw_action()

        assert output.getvalue() == encode(records)
