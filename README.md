# Hamtrain

Hamtrain is most likely only useful for germans, nevertheless, I’ll put the
readme in English.

Hamtrain is split in two utilities: ``hamtrain.py`` and ``itutrain.py``. The
former is used to learn the radio bands and the constraints on power and
bandwidth in these bands. The latter is used to learn the country prefixes.

## ``hamtrain.py``

### Preparation

``hamtrain.py`` needs a database file to know what to teach you. ``hamtrain.py``
is a bit ugly in code, so it will always open the ``db`` file in the current
working directory.

You can either symlink ``db_master`` to ``db`` or create your own copy of
``db_master``, possibly eliding entries you do not want to learn.

### Usage

With a ``db`` file, you can simply invoke ``hamtrain.py``. It will ask you
questions and tell you how wrong you were afterwards ☺. To stop, use Ctrl+D or
Ctrl+C. It will then print a score.

    $ ./hamtrain.py

## ``itutrain.py``

### General usage

``itutrain.py`` has a more proper CLI than ``hamtrain.py``:

    usage: itutrain.py [-h] [-d DATABASE] {train,dumpdb} ...

    positional arguments:
      {train,dumpdb}

    optional arguments:
      -h, --help            show this help message and exit
      -d DATABASE, --db DATABASE, --database DATABASE

You need to pass a database file (but it defaults to ``itudb`` which is included
in this repository). Again you could customize this. Inside ``itudb``, you can
use ``#prio <number>`` directives to tell ``itutrain.py`` how important it is to
you to learn these prefixes.

### Training

    usage: itutrain.py train [-h] trainfile

    positional arguments:
      trainfile

    optional arguments:
      -h, --help  show this help message and exit

You must pass a *trainfile*. This is a file where ``itutrain.py`` records your
progress to be able to teach you the prefixes efficiently. At least that works
for me ☺. This is separate from the database file and will be created if it
doesn’t exist.

***Note:*** Do not use trainfiles from untrusted sources. They can execute
arbitrary code when loaded ☺.

In train mode, ``itutrain.py`` will ask you a set of questions, and afterwards
show you your score. Aborting with Ctrl+C or Ctrl+D will terminate
``itutrain.py``, while still updating the *trainfile*, but without showing you
your score.
