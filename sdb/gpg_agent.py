import os
import socket

class GpgAgent(object):
    def __init__(self, socket_file=None):
        if not socket_file:
            socket_file, _, _ = os.environ['GPG_AGENT_INFO'].partition(':')

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

    def get_passphrase(self, cache_id, error='X', prompt='X', description='X'):
        error = error.replace(' ', '+')
        prompt = prompt.replace(' ', '+')
        description = description.replace(' ', '+')
        self.writeline(
            "GET_PASSPHRASE --data {cache_id} {error} {prompt} {description}".format(
                cache_id=cache_id,
                error=error,
                prompt=prompt,
                description=description
        ))
        self.socket.flush()

        pw_line = self.socket.readline()
        if pw_line == 'OK\n':
            return ''
        assert pw_line.startswith('D '), "%r is not a data line" % pw_line
        self.check_ok()
        return pw_line[2:-1]

    def clear_passphrase(self, cache_id):
        self.writeline(
            "CLEAR_PASSPHRASE {cache_id}".format(cache_id=cache_id)
        )
        self.check_ok()
