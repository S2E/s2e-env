# `s2e-env`

A command-line tool for creating and administering isolated development
environments for [S2E](http://s2e.systems). Each environment contains all the
tools required to run S2E plus one or more "projects". A project is essentially
an analysis target. For example, one project might be the analysis of a [CGC
binary](https://github.com/CyberGrandChallenge/samples), while another project
might be the analysis of the ``file`` program from
[Coreutils](https://www.gnu.org/software/coreutils/coreutils.html).

# Prerequisites

We assume that you are working on an Ubuntu 14.04 or 16.04 64-bit OS.
[Repo](https://code.google.com/p/git-repo/) only works with Python 2.7, so you
should use Python 2.7 too. You will also need `gcc` and `python-dev` installed.

Some commands (such as basic block coverage) require a disassembler. Supported
disassemblers include:

* [IDA Pro](https://www.hex-rays.com/products/ida/)
* [Radare](https://rada.re/). Requires
  [r2pipe](https://pypi.python.org/pypi/r2pipe)
* [Binary Ninja](https://binary.ninja/). Requires GUI-less processing

# Install

```
git clone https://github.com/S2E/s2e-env.git
cd s2e-env
pip install .
```

If you wish to install `s2e-env` to a Python
[virtual environment](http://docs.python-guide.org/en/latest/dev/virtualenvs/),
please create and activate this virtualenv before installing `s2e-env` with
pip.

# Configuring

`s2e-env` is configurable in two ways. Firstly, there is a global YAML
configuration file located in `s2e_env/dat/config.yaml`. This configuration
file controls how *all* environments are created. You are not normally required
to modify the settings in this file. If you wish to customize how environments
are created, you should edit this file **before** running `pip install` to
install `s2e-env`.

For example, you may want to clone the S2E source repos via SSH rather than
HTTPS, in which case you would set the `repos`, `url` option to
`git@github.com:S2E`.

A second YAML configuration file, `s2e.yaml`, is created in each S2E
environment. This contains settings that are local to each S2E environment. For
example, if you want to generate basic block coverage, you will also have to
set the `ida`, `path` option.

# Usage

The package can be installed via `pip`, thus making the `s2e` command
available.

To list the available commands:

```
s2e help --commands
```

To get help on a particular command:

```
s2e <subcommand> --help
```

Most commands use the `S2EDIR` environment variable so that commands can be run
from any directory. `S2EDIR` can be set by sourcing `install/bin/s2e_activate`
in your environment directory. Sourcing this file also makes `s2e_deactivate`
available, which unsets S2E environment variables.

Alternatively, most commands take an optional `--env /path/to/env` argument.
This argument can be used to specify the path to the S2E environment you want
to execute the command in.

Note that **one of** the `S2EDIR` environment variable or `--env` option
**must** be used.

## Workflow

Each command follows the Unix philosophy that each command ("tool") consists of
a small program designed to accomplish a single, particular task, rather than
trying to develop monolithic commands to do a number of tasks.

A typical workflow is therefore:

1. Run `s2e init $DIR` to create a new S2E environment in `$DIR`. This will
   create the environment, install dependencies (unless `--skip-dependencies`
   is used) and fetch all of the S2E engine code.
2. Activate the environment via `. $DIR/install/bin/s2e_activate`.
3. Look around the source code, make some modifications, etc. Then when you are
   ready to build run `s2e build`.
4. You'll need some images to analyze your software in! See what images are
   available with `s2e image_build`.
5. Run `s2e image_build $TEMPLATE` to build one of the images listed in the
   previous step. This will create the image in the `images` directory.
6. Use `s2e new_project` to create a new analysis project. This will create all
   the launch scripts, configuration files and bootstrap scripts necessary to
   perform the analysis on a given target. Currently Linux ELF executables,
   Decree CGC binaries, Windows PE executables and Windows DLLs can be
   targeted with the `new_project` command.
7. Change into the project directory and run the S2E analysis with the
   `launch-s2e.sh` script.
8. After your analysis has finished, a number of subcommands exist to analyze
   and summarize your results, e.g. the ``coverage`` and ``execution_trace``
   subcommands.

Other useful commands:

* `s2e info` can be used to display a summary of the S2E environment.
* To download the latest changes from the git repositories, run `s2e update`.
* Projects can be shared using `s2e export_project` and `s2e import_project`.

## Environment structure

`s2e init` generates the following directory structure in your S2E environment.

```
.
├── build/
├── images/
├── install/
├── projects/
├── s2e.yaml
├── source/
```

* `build`: Staging directory for builds
* `images`: Images created with `s2e image_build` go here
* `install`: Installed executables, libraries, header files, etc.
* `projects`: Analysis projects created with `s2e new_project` go here
* `s2e.yaml`: A per-environment configuration file. This file is also used to
  "mark" the directory as an S2E environment, so please do not delete it!
* `source`: Source code repositories

# Extending

Extending with new commands is relatively simple. `s2e-env` is heavily
influenced by [Django's](https://github.com/django/django) command subsystem,
so there is a wealth of documentation already available (for example,
[here](https://docs.djangoproject.com/en/1.10/howto/custom-management-commands/)).

For example, to create a command `foo`:

1. Create a new Python module `s2e_env/commands/foo.py`
2. In `foo.py` define a `Command` class that extends
    * `s2e_env.command.BaseCommand` - The base class. Probably not that useful
      to inherit directly from this class
    * `s2e_env.command.EnvCommand` - For commands that operate on an existing
      S2E environment
    * `s2e_env.command.ProjectCommand` - For commands that operate on an
      existing analysis project
3. The only method required in your `Command` class is
  `handle(self, *args, **options)`. This method contains your command logic
4. You may optionally define an `add_arguments(self, parser)` method for
   parsing command-line arguments specific to the `foo` command. The `parser`
   argument is essentially an `ArgumentParser` from the
   [argparse](https://docs.python.org/3/library/argparse.html) library.
   
   If you extend from `EnvCommand` you **must** call the super `add_arguments`,
   i.e.:

   ```python
   def add_arguments(self, parser):
       super(Command, self).add_arguments(parser)
       # Add your arguments/options here
   ```

5. On error, an `s2e_env.command.CommandError` should be raised
6. Use the `logging` module for printing messages. When calling
   `logging.getLogger` the command name should be provided as the logger name.

# Running commands from your code

Like Django's command subsystem (see
[here](https://docs.djangoproject.com/en/1.10/ref/django-admin/#running-management-commands-from-your-code)),
`s2e-env` also allows you to call commands programatically
via the `call_command` function.

Example:

```python
from s2e_env.manage import call_command
from s2e_env.commands.new_project import Command as NewProjectCommand

def create_s2e_project(target_path, s2e_env_path):
    call_command(NewProjectCommand(), target_path, env=s2e_env_path, force=True)
```
