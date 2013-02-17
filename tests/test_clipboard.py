import threading
import time

from sdb.clipboard import *


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


def test_set_clipboard_once():
    class Thread(threading.Thread):
        def run(self):
            time.sleep(1)
            self.contents = get_clipboard()
    t = Thread()
    t.start()
    set_clipboard(b'before')
    set_clipboard_once(b'foo')
    t.join()
    assert t.contents == b'foo'
    # we should restore the previous value
    assert get_clipboard() == b'before'


def test_set_clipboard_once_noclobber():
    class Thread(threading.Thread):
        def run(self):
            time.sleep(1)
            set_clipboard(b'asdf')
            self.contents = get_clipboard()
    t = Thread()
    t.start()
    set_clipboard(b'before')
    set_clipboard_once(b'foo')
    t.join()
    assert t.contents == b'asdf'
    # if the selection belongs to someone else, we shouldn't restore
    assert get_clipboard() == b'asdf'


def test_clipboard_no_x():
    import os
    d = os.environ['DISPLAY']
    try:
        del os.environ['DISPLAY']
        try:
            set_clipboard(b'a')
            assert not "must raise exception"
        except ClipboardException as e:
            assert e.output.startswith(b"xsel: Can't open display: ")
    finally:
        os.environ['DISPLAY'] = d

def test_set_clipboard_once_no_x():
    import os
    d = os.environ['DISPLAY']
    try:
        del os.environ['DISPLAY']
        try:
            set_clipboard_once(b'a')
            assert not "must raise exception"
        except ClipboardException as e:
            assert e.output.startswith(b"xsel: Can't open display: ")
    finally:
        os.environ['DISPLAY'] = d
