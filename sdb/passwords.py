import ast
import time
import string
import math
import os
import sys
import tempfile
import select
from operator import itemgetter
from contextlib import contextmanager
from getpass import getpass
import random; random = random.SystemRandom()

import sdb.subprocess_compat as subprocess
from sdb.diceware import WORDS


def force_bytes(s):
    try:
        return s.encode('utf-8')
    except (AttributeError, UnicodeDecodeError):
        return s


def encode(records):
    res = []
    for record in records:
        res.append(repr(record))
    return ('\n'.join(res) + '\n').encode('utf-8')


def decode(str):
    records = []
    for line in str.decode('utf-8').split('\n'):
        if line:
            records.append(ast.literal_eval(line))
    return records


class ClipboardException(subprocess.CalledProcessError):
    def __init__(self, returncode, cmd, output=None):
        # Python 2.6 compatibility -- CalledProcessError doesn't take output in
        # that version
        super(ClipboardException, self).__init__(returncode, cmd)
        self.output = output
    pass


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


CASE_ALPHABET = string.ascii_letters
ALPHANUMERIC = CASE_ALPHABET + string.digits
EVERYTHING = ALPHANUMERIC + string.punctuation


def gen_password(choices=ALPHANUMERIC, length=10):
    return ''.join(random.choice(choices) for i in range(length))


def requirements_satisfied(requirements, str):
    return all([i in str for i in requirements])


def gen_password_require(requirements, choices=ALPHANUMERIC, length=10):
    """
    Generate a password containing all the characters in requirements
    """
    if len(requirements) > length or not requirements_satisfied(requirements, choices):
        raise Exception(
            "That's impossible, you can't make a password containing %r with only %r!" % (
                requirements, choices))
    while True:
        pw = gen_password(choices, length)
        if requirements_satisfied(requirements, pw):
            return pw


def gen_password_entropy(entropy, choices=ALPHANUMERIC):
    """
    Generates a password of the desired entropy, calculating the length as
    required.
    """
    required_length = int(math.ceil(entropy / math.log(len(choices), 2)))
    return gen_password(choices=choices, length=required_length)


def match(needle, haystack):
    score = 1
    j = 0
    last_match = 0
    for c in needle:
        while j < len(haystack) and haystack[j] != c:
            j += 1
        if j >= len(haystack):
            return 0
        score += 1 / (last_match + 1.)
        last_match = j
        j += 1
    return score


def record_score(term, records):
    return match(term, records[0] + records[1] + records[3])


def search(term, records):
    records = [(record_score(term, i), i) for i in records]
    records = list(filter(itemgetter(0), records))
    records.sort(key=itemgetter(0), reverse=True)
    return [i[1] for i in records]


def is_unique_list(lst):
    return len(lst) == len(set(lst))


def disambiguate(records):
    choices = [itemgetter(0),
               itemgetter(0, 1),
               itemgetter(0, 1, 3)]
    for choice in choices:
        result = list(map(choice, records))
        if is_unique_list(result):
            return result
    # just in case none were unique
    return records


class GPGException(Exception):
    pass

class IncorrectPasswordException(GPGException):
    pass

class InvalidEncryptedFileException(GPGException):
    pass

class FileCorruptionException(GPGException):
    pass


def gpg_exception_factory(returncode, message):
    if returncode == 2:
        if b'decryption failed: bad key' in message:
            return IncorrectPasswordException(message)
        if b'CRC error;' in message:
            return FileCorruptionException(message)
        if b'fatal: zlib inflate problem: invalid distance' in message:
            return FileCorruptionException(message)
        if b'decryption failed: invalid packet' in message:
            return FileCorruptionException(message)
        if b'no valid OpenPGP data found':
            return InvalidEncryptedFileException(message)
    return Exception("unkown error", returncode, message)


def dencrypt(command, pw, data):
    """
    Encrypts or decrypts, by running command
    """
    if '\n' in pw:
        raise Exception('Newlines not allowed in passwords')
    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    proc.stdin.write(force_bytes(pw))
    proc.stdin.write(b'\n')
    proc.stdin.write(data)
    output, erroroutput = proc.communicate()
    if proc.returncode != 0:
        raise gpg_exception_factory(proc.returncode, erroroutput)
    return output


def encrypt(pw, data):
    return dencrypt(
        ['gpg', '-c',
         '--passphrase-fd', '0',
         '--batch',
         '--armor',
         '--cipher-algo', 'AES',
         '--digest-algo', 'SHA256'],
        pw,
        data,
    )


def decrypt(pw, data):
    return dencrypt(
        ['gpg', '-d', '--passphrase-fd', '0', '--batch'],
        pw,
        data
    )


def get_tmp_file(filename):
    file_parts = os.path.split(filename)
    return os.path.join(*file_parts[:-1] + ('.' + file_parts[-1].lstrip('.') + '.tmp',))


def get_backup_file(filename):
    file_parts = os.path.split(filename)
    return os.path.join(*file_parts[:-1] + ('.' + file_parts[-1].lstrip('.') + '.bak',))


@contextmanager
def atomic_replace(filename):
    """
    ::
        with atomic_replace(filename) as f:
            f.write('asdf')

        with atomic_replace(filename) as f:
            f.write('asdf')
            raise Exception
        # nothing happens to the file
    """
    tmpfile_name = get_tmp_file(filename)
    fd = os.open(tmpfile_name, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
    try:
        f = os.fdopen(fd, "w+b")
        yield f
        f.flush()
        os.fsync(fd)  # fdatasync? I don't know
        f.seek(0)
        new_content = f.read()
        if not new_content:
            raise Exception("I don't think you want to blank this file...")
        try:
            with open(filename, 'rb') as current_f:
                current_content = current_f.read()
        except IOError:
            current_content = b''
        if current_content != new_content:
            with open(get_backup_file(filename), 'w+b') as backup_file:
                backup_file.write(current_content)
    except:
        # If there was an exception, remove the temporary file and reraise
        os.unlink(tmpfile_name)
        raise
    else:
        # No exception, rename the temp file over the original
        os.rename(tmpfile_name, filename)
    finally:
        f.close()


def edit_in_editor(current):
    EDITOR = os.environ.get('EDITOR', 'vim')
    with tempfile.NamedTemporaryFile(mode='w+') as f:
        try:
            f.write(current)
            f.flush()
            subprocess.call([EDITOR, f.name])
            f.seek(0)
            return f.read()
        finally:
            # don't leave potentially private data lying around
            f.write('0' * os.path.getsize(f.name))
            f.flush()


def pretty_record(record):
    s = '%s@%s' % (record[1], record[0])
    if record[3]:
        s += ': ' + record[3]
    return s


class InteractiveSession(object):
    def __init__(self, args, output=sys.stdout, input=sys.stdin, password=None):
        self.args = args
        self.file = args.file
        self.password = password or getpass()
        self.output = output
        self.input = input

    def prompt(self, prompt='', required=True, password=False):
        while True:
            if password and self.input == sys.stdin:
                line = getpass(prompt)
            else:
                self.output.write(prompt)
                self.output.flush()
                line = self.input.readline().rstrip('\n')
            if not required or line:
                return line

    def get_record(self, domain=None):
        domain = domain or self.prompt('Domain: ')
        username = self.prompt('Username: ')
        password = self.prompt(
            'Password [blank to generate]: ',
            required=False,
            password=True
        ) or gen_password_entropy(128)
        notes = self.prompt('Notes: ', required=False)

        return (domain, username, password, notes)

    def edit_record(self, record):
        new_record = list(record)
        new_record[0] = self.prompt('Name [%s]: ' % record[0], required=False) or record[0]
        new_record[1] = self.prompt('Username [%s]: ' % record[1], required=False) or record[1]
        pw = self.prompt('Password []/g: ', required=False, password=True) or record[2]
        if pw == 'g':
            new_record[2] = gen_password_entropy(128)
        elif pw:
            new_record[2] = pw
        self.output.write("Notes: %s\n" % record[3])
        edit = self.prompt('Edit? [n]: ', required=False) or 'n'
        if edit[0] == 'y':
            new_record[3] = edit_in_editor(record[3])
        return tuple(new_record)

    def find_record(self, query, records):
        possibilities = search(query, records)
        if len(possibilities) > 1:
            choices = disambiguate(possibilities)
            for i, choice in enumerate(choices):
                self.output.write('%s) %s\n' % (i, choice))
            choice = self.prompt('Which did you mean? [0]: ', required=False) or 0
            return possibilities[int(choice)]
        else:
            return possibilities[0]

    def read_records(self):
        try:
            with open(self.file, 'rb') as f:
                return decode(decrypt(self.password, f.read()))
        except IOError:
            return []

    def add_action(self):
        record = self.get_record(self.args.domain or self.prompt('Domain: '))

        def add(records):
            return records + [record]
        self.edit_transaction(add)

    def show_action(self, clipboard=10):
        record = self.find_record(self.args.domain or self.prompt("Domain: "), self.read_records())
        self.output.write(pretty_record(record))
        self.output.write("\n")
        if clipboard:
            try:
                self.output.write("username in clipboard\n")
                set_clipboard_once(record[1])
                self.output.write("password in clipboard\n")
                set_clipboard_once(record[2])
            except ClipboardException as e:
                self.output.write("couldn't set clipboard: %s\n" % e.output.split('\n')[0])
                self.output.write(record[2])
                self.output.write("\n")
        else:
            return record[2]

    def edit_transaction(self, callback):
        with atomic_replace(self.file) as out:
            records = callback(self.read_records())
            assert isinstance(records, list)
            if not is_unique_list(records):
                raise Exception("You have two identical records. I don't think you want this.")
            out.write(encrypt(self.password, encode(records)))
            out.seek(0)
            assert records == decode(decrypt(self.password, out.read()))

    def edit_action(self):
        def edit(records):
            record = self.find_record(self.args.domain or self.prompt('Domain: '), records)
            new_record = self.edit_record(record)
            for i, choice in enumerate(records):
                if choice == record:
                    records[i] = tuple(new_record)
            return records
        self.edit_transaction(edit)

    def delete_action(self):
        def delete(records):
            record = self.find_record(self.args.domain or self.prompt('Domain: '), records)
            self.output.write(pretty_record(record))
            self.output.write('\n')
            confirm = self.prompt('Really? [n]: ', required=False) or 'n'
            if confirm[0] == 'y':
                for i, choice in enumerate(records):
                    if choice == record:
                        del records[i]
            else:
                self.output.write("Ok, cancelled\n")
            return records
        self.edit_transaction(delete)

    def raw_action(self):
        try:
            # PY3
            output = self.output.buffer
        except AttributeError:
            output = self.output
        output.write(encode(self.read_records()))
