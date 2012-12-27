# sdb

A command-line password safe.

[![Build Status](https://travis-ci.org/gavinwahl/sdb.png?branch=master)](https://travis-ci.org/gavinwahl/sdb)

# Usage

    $ sdb gmail
    Password:
    something@gmail.com
    # password in clipboard for 10 seconds

    $ sdb g
    Password:
    1.) google.com
    2.) github.com
    #> 2
    githubusername

    $ sdb --add foobar.com
    Password:
    Username:
    Password (blank to generate):
    Notes []:

    $ sdb --edit foo
    Password:
    Name [foo.com]:
    Username [foo@foo.com]:
    Password []:
    Notes (edit in editor y/n):

    $ sdb --delete foo
    username@foo.com
    Really? [n]:
