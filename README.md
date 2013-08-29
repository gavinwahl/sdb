# sdb

A command-line password safe.

[![Build Status](https://travis-ci.org/gavinwahl/sdb.png?branch=master)](https://travis-ci.org/gavinwahl/sdb)

## Installation

sdb depends on `xsel`.  If you are on a Debian-based Linux distro, you can
install `xsel` by typing:

    # apt-get install xsel

You can install sdb straight from GitHub.

    $ pip install -e git://github.com/gavinwahl/sdb.git@master#egg=sdb

## Usage

To save a password

    $ sdb add foobar.com
    Password:
    Username: bill
    Password [blank to generate]:
    Notes:

To retrieve that password

    $ sdb show foobar.com
    Password:
    bill@foobar.com

**Note:** The username and then the password will be put in the X clipboard
until you press enter or paste them. If you're not running X (or there is no
`$DISPLAY`), the password will be printed.

Alternatively, you can see all of the passwords you have stored by typing

    $ sdb raw
    Password:
    ('foobar.com', 'bill', 'XXXXXXXXXXXXXXXXXXX', '')

The `show` command will list several choices if more than one matches.

    $ sdb show f
    Password:
    0) ('foobar.com', 'bill', 'XXXXXXXXXXXXXXXXXXX', '')
    1) ('foofoo.com', 'bill', 'XXXXXXXXXXXXXXXXXXX', '')
    Which did you mean? [0]:

You can change your password if you like

    $ sdb edit foo
    Password:
    Name [foo.com]:
    Username [foo]:
    Password []/g:
    Notes:
    Edit? [n]:

If you want to delete a password you can do that too.

    $ sdb delete foo
    Password:
    username@foo.com
    Really? [n]:

## Remembering the master password

sdb will automatically use gpg-agent if it is running. To start gpg-agent, you
can use

    sdb agent
