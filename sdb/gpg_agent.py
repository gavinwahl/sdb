import os
import socket


class AgentError(Exception):
    """
    Raised when there's a problem with gpg-agent -- like the user cancelling.

    what exception should this inherit from?
    """
    pass


class GpgAgent(object):
    def __init__(self, socket_file=None, info_file=None):
        if not socket_file:
            try:
                env = os.environ['GPG_AGENT_INFO']
            except KeyError:
                if info_file:
                    with open(info_file) as f:
                        _, _, env = f.read().partition('=')
                else:
                    raise AgentError('No gpg-agent available')
            socket_file, _, _ = env.partition(':')

        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(socket_file)
        self.socket = s.makefile()
        assert self.socket.readline().startswith('OK')

        self.socket.write('OPTION display={display}\r\n'.format(display=os.environ['DISPLAY']))
        self.socket.flush()
        assert self.socket.readline().startswith('OK')

    def check_ok(self):
        self.socket.flush()
        ok_line = self.socket.readline()
        assert ok_line == "OK\n", "%r is not ok!" % ok_line

    def writeline(self, line):
        self.socket.write(line + '\n')
        self.socket.flush()

    def get_passphrase(self, cache_id, error='X', prompt='X', description='X', repeat=0):
        error = error.replace(' ', '+')
        prompt = prompt.replace(' ', '+')
        description = description.replace(' ', '+')
        self.writeline(
            "GET_PASSPHRASE --repeat={repeat} --data {cache_id} {error} {prompt} {description}".format(
                cache_id=cache_id,
                error=error,
                prompt=prompt,
                description=description,
                repeat=repeat,
            )
        )
        self.socket.flush()

        pw_line = self.socket.readline()
        if pw_line == 'OK\n':
            return ''
        if pw_line.startswith('ERR '):
            raise AgentError(pw_line)
        assert pw_line.startswith('D '), "%r is not a data line" % pw_line
        self.check_ok()
        return pw_line[2:-1]

    def clear_passphrase(self, cache_id):
        self.writeline(
            "CLEAR_PASSPHRASE {cache_id}".format(cache_id=cache_id)
        )
        self.check_ok()
