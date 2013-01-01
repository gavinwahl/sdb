import subprocess
import select
import time
import sys

from sdb.util import force_bytes


class ClipboardException(subprocess.CalledProcessError):
    def __init__(self, returncode, cmd, output=None):
        # Python 2.6 compatibility -- CalledProcessError doesn't take output in
        # that version
        super(ClipboardException, self).__init__(returncode, cmd)
        self.output = output


def set_clipboard(str):
    command = ['xsel', '-pi']
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    _, stderr = proc.communicate(str)
    if proc.returncode != 0:
        raise ClipboardException(proc.returncode, command, stderr)


def get_clipboard():
    try:
        return subprocess.check_output(['xsel', '-po'], stderr=subprocess.PIPE)
    except subprocess.CalledProcessError:
        # sometimes there is no clipboard
        return b''


def set_clipboard_once(str):
    """
    Set the clipboard to str, and wait for it to be retrieved once.
    """
    current = get_clipboard()
    command = ['xsel', '-pi', '-vvvv', '-n']
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    proc.stdin.write(force_bytes(str))
    proc.stdin.close()
    expected_returncode = 0
    stderr_output = b''
    while True:
        rfds, _, _ = select.select([sys.stdin, proc.stderr], [], [])
        if sys.stdin in rfds:
            # line from std == cancel
            sys.stdin.readline()
            proc.kill()
            expected_returncode = -9
            break
        else:
            line = proc.stderr.readline()
            stderr_output += line
        if not line:
            # xsel quit, probably because someone else took ownership of the
            # selection
            break
        elif b'(UTF8_STRING)' in line or b'(TEXT)' in line or b'(XSEL_DATA)' in line:
            # someone retrieved the selection, all done
            proc.kill()
            expected_returncode = -9
            break
    proc.wait()
    if proc.returncode != expected_returncode:
        raise ClipboardException(proc.returncode, command, stderr_output)
    if get_clipboard() == b'':
        set_clipboard(current)


def copy_to_clipboard(str, timeout=10):
    str = force_bytes(str)
    current_clipboard = get_clipboard()
    set_clipboard(str)
    try:
        time.sleep(timeout)
    finally:
        # if the clipboard has changed in the meantime, try not to overwrite the
        # new value. still a race condition, but this should be better
        if str == get_clipboard():
            set_clipboard(current_clipboard)
