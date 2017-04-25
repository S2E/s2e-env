# `s2e-env`

A command-line tool for creating and administering isolated development
environments for [S2E](http://s2e.systems). Each environment contains all the
tools required to run S2E plus one or more "projects". A project is essentially
an analysis target. For example, one project might be the analysis of a [CGC
binary](https://github.com/CyberGrandChallenge/samples), while another project
might be the analysis of the ``file`` program from
[Coreutils](https://www.gnu.org/software/coreutils/coreutils.html).

# Prerequisites

We assume that you are working on Ubuntu 14.04 (or newer) 64-bit OS.
[Repo](https://code.google.com/p/git-repo/) only works with Python 2.7, so you
should use Python 2.7 too.

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

`s2e-env` can be configured via a YAML configuration file. This configuration
file is located in `s2e_env/dat/config.yaml`. If you wish to customize your
`s2e-env` install you can edit this file before running `pip install`.

For example, you may want to clone the S2E source repos via SSH rather than
HTTPS, in which case you would set the `repos`, `url` option to
`git@github.com:S2E`. If you want to generate basic block coverage, you will
also have to set the `ida`, `path` option.

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

All commands take an optional `--env /path/to/env` argument to specify the
path to the S2E environment you want to execute the command in. If not provided
this path defaults to the current working directory. For the workflow described
below it is easiest to execute all commands from within your S2E environment
directory.

## Workflow

Each command follows the Unix philosophy that each command ("tool") consists of
a small program designed to accomplish a single, particular task, rather than
trying to develop monolithic commands to do a number of tasks.

A typical workflow is therefore:

1. Run `s2e init $DIR` to create a new S2E environment in `$DIR`. This will
   create the environment, install dependencies (unless `--skip-dependencies`
   is used) and fetch all of the S2E engine code.
2. Look around the source code, make some modifications, etc. Then when you are
   ready to build run `s2e build`.
3. You'll need some images to analyze your software in! See what images are
   available with `s2e image_build`.
4. Run `s2e image_build $TEMPLATE` to build one of the images listed in the
   previous step. This will create the image in the `images` directory.
5. Use `s2e new_project` to create a new analysis project. This will create all
   the launch scripts, configuration files and bootstrap scripts necessary to
   perform the analysis on a given target.
6. Change into the project directory and run the S2E analysis with the
   `launch-s2e.sh` script.
7. After your analysis has finished, a number of subcommands exist to analyze
   and summarize your results, e.g. the ``coverage`` subcommand, etc.

The `s2e info` command can be used to display a summary of the S2E environment.
To grab the latest changes from the git repositories, run `s2e update`.

## Environment structure

`s2e init` generates the following directory structure in your S2E environment.

```
.
├── build
├── images
├── install
├── projects
├── source
```

* `build`: Staging directory for builds
* `images`: Images created with `s2e image_build` go here
* `install`: Installed executables, libraries, header files, etc.
* `projects`: Analysis projects created with `s2e new_project` go here
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
