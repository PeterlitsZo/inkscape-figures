#!/usr/bin/env python3

import os
import logging
import subprocess
import warnings
from pathlib import Path
from shutil import copy
from daemonize import Daemonize
import click
import platform
import pyperclip
from appdirs import user_config_dir

logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))
log = logging.getLogger('inkscape-figures')

inkscape_path = repr("/mnt/c/Program Files/Inkscape/inkscape.exe")

# ---[ units ]---------------------------------------------------------------------------

def mkdir_chain(path: Path):
    """ if path do not exists, try to make it. """
    path = Path(path)
    if not path.exists():
        for parent in reversed(path.parents):
            if not parent.exists():
                parent.mkdir()
        path.mkdir()


def indent(text, indentation=0):
    """ add indent to text """
    lines = text.split('\n');
    return '\n'.join(" " * indentation + line for line in lines)


def beautify(name):
    """ make file name looks better """
    return name.replace('_', ' ').replace('-', ' ').title()


def latex_template(name, title):
    """ return latex pic string """
    return (
         r"\begin{figure}[ht]"                           '\n'
         r"    \centering"                               '\n'
        rf"    \import{{./fig/}}{{{name}.pdf_tex}}"      '\n'
        rf"    \caption{{{title}}}"                      '\n'
        rf"    \label{{fig:{name}}}"                     '\n'
         r"\end{figure}"
    )


def inkscape(command: str):
    """ run inkscape with command """
    with warnings.catch_warnings():
        # leaving a subprocess running after interpreter exit raises a
        # warning in Python3.7+
        warnings.simplefilter("ignore", ResourceWarning)
        log.info('run ' + repr(inkscape_path + ' ' + str(command)))
        return subprocess.run(inkscape_path + ' ' + str(command), shell=True)


# From https://stackoverflow.com/a/67692
def import_file(name, path):
    """ import file, like its name """
    import importlib.util as util
    spec = util.spec_from_file_location(name, path)
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---[ Load user config ]----------------------------------------------------------------

user_dir = Path(user_config_dir("inkscape-figures", "Castel"))

if not user_dir.is_dir():
    user_dir.mkdir()

roots_file =  user_dir / 'roots'
template = user_dir / 'template.svg'
config = user_dir / 'config.py'

if not roots_file.is_file():
    roots_file.touch()

if not template.is_file():
    source = str(Path(__file__).parent / 'template.svg')
    destination = str(template)
    copy(source, destination)

if config.exists():
    config_module = import_file('config', config)
    latex_template = config_module.latex_template
    inkscape_path = config_module.inkscape_path


def add_root(path):
    path = str(path)
    roots = get_roots()
    if path in roots:
        return None

    roots.append(path)
    roots_file.write_text('\n'.join(roots))


def get_roots():
    return [root for root in roots_file.read_text().split('\n') if root != '']


# ---[ commands ]------------------------------------------------------------------------

@click.group()
def cli():
    pass


# ---[ commands - watch ]----------------------------------------------------------------

# @cli.command()
# @click.option('--daemon/--no-daemon', default=True)
# def watch(daemon):
#     """
#     Watches for figures.
#     """
#     if platform.system() == 'Linux':
#         watcher_cmd = watch_daemon_inotify
#     else:
#         watcher_cmd = watch_daemon_fswatch
# 
#     if daemon:
#         log.info("Watching figures. (Daemon Mode)")
#         daemon = Daemonize(app='inkscape-figures',
#                            pid='/tmp/inkscape-figures.pid',
#                            action=watcher_cmd)
#         daemon.start()
#     else:
#         log.info("Watching figures. (Not Daemon Mode)")
#         watcher_cmd()


def maybe_recompile_figure(filepath):
    filepath = Path(filepath)
    # A file has changed
    if filepath.suffix != '.svg':
        log.debug('File has changed, but is nog an svg {}'.format(
            filepath.suffix))
        return

    log.info('Recompiling %s', filepath)

    pdf_path = filepath.parent / (filepath.stem + '.pdf')
    name = filepath.stem

    # remove a line because i think the output under windows is differe with linux
    # inkscape_version = subprocess.check_output([inkscape_path, '--version'], universal_newlines=True)
    # log.debug(inkscape_version)

    command = (f"{filepath} --export-area-page --export-dpi 300 "
               f"--export-pdf {pdf_path} --export-latex {filepath}")

    log.debug('Running command:')
    log.debug('inkscape ' + command)

    # Recompile the svg file
    completed_process = inkscape(command)

    if completed_process.returncode != 0:
        log.error('Return code %s', completed_process.returncode)
    else:
        log.debug('Command succeeded')

    # Copy the LaTeX code to include the file to the clipboard
    pyperclip.copy(latex_template(name, beautify(name)))


# def watch_daemon_inotify():
#     import inotify.adapters
#     from inotify.constants import IN_CLOSE_WRITE
#     print('fdsa')
# 
#     while True:
#         roots = get_roots()
# 
#         # Watch the file with contains the paths to watch
#         # When this file changes, we update the watches.
#         i = inotify.adapters.Inotify()
#         i.add_watch(str(roots_file), mask=IN_CLOSE_WRITE)
# 
#         # Watch the actual figure directories
#         log.info('Watching directories: ' + ', '.join(get_roots()))
#         for root in roots:
#             try:
#                 i.add_watch(root, mask=IN_CLOSE_WRITE)
#             except Exception:
#                 log.debug('Could not add root %s', root)
# 
#         for event in i.event_gen(yield_nones=False):
#             (_, type_names, path, filename) = event
# 
#             # If the file containing figure roots has changes, update the
#             # watches
#             if path == str(roots_file):
#                 log.info('The roots file has been updated. Updating watches.')
#                 for root in roots:
#                     try:
#                         i.remove_watch(root)
#                         log.debug('Removed root %s', root)
#                     except Exception:
#                         log.debug('Could not remove root %s', root)
#                 # Break out of the loop, setting up new watches.
#                 break
# 
#             # A file has changed
#             path = Path(path) / filename
#             maybe_recompile_figure(path)
# 
# 
# def watch_daemon_fswatch():
#     print('fdsa')
#     while True:
#         roots = get_roots()
#         log.info('Watching directories: ' + ', '.join(roots))
#         # Watch the figures directories, as weel as the config directory
#         # containing the roots file (file containing the figures to the figure
#         # directories to watch). If the latter changes, restart the watches.
#         with warnings.catch_warnings():
#             warnings.simplefilter("ignore", ResourceWarning)
#             p = subprocess.Popen(
#                     ['fswatch', *roots, str(user_dir)], stdout=subprocess.PIPE,
#                     universal_newlines=True)
# 
#         while True:
#             filepath = p.stdout.readline().strip()
# 
#             # If the file containing figure roots has changes, update the
#             # watches
#             if filepath == str(roots_file):
#                 log.info('The roots file has been updated. Updating watches.')
#                 p.terminate()
#                 log.debug('Removed main watch %s')
#                 break
#             maybe_recompile_figure(filepath)



# ---[ commands - create ]---------------------------------------------------------------

@cli.command()
@click.argument('title')
@click.argument(
    'root',
    default=Path.cwd() / 'fig',
    type=click.Path(exists=False, file_okay=False, dir_okay=True)
)
def create(title, root):
    """
    Creates a figure.

    First argument is the title of the figure
    Second argument is the figure directory.

    """
    title = title.strip()
    file_name = title.replace(' ', '-').lower() + '.svg'
    figures = Path(root).absolute()
    mkdir_chain(figures)

    figure_path = figures / file_name

    # If a file with this name already exists, append a '2'.
    if figure_path.exists():
        print(title + ' 2')
        return

    copy(str(template), str(figure_path))
    add_root(figures)
    inkscape(figure_path)

    # Print the code for including the figure to stdout.
    # Copy the indentation of the input.
    leading_spaces = len(title) - len(title.lstrip())
    print(indent(latex_template(figure_path.stem, title), indentation=leading_spaces))
    maybe_recompile_figure(figure_path)

# ---[ commands - edit ]-----------------------------------------------------------------

@cli.command()
@click.argument(
    'root',
    default=Path.cwd() / 'fig',
    type=click.Path(exists=True, file_okay=False, dir_okay=True)
)
def edit(root):
    """
    Edits a figure.

    First argument is the figure directory.
    """

    figures = Path(root).absolute()
    mkdir_chain(figures)

    # Find svg files and sort them
    files = figures.glob('*.svg')
    files = sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)

    # Open a selection dialog using a gui picker like rofi
    names = [beautify(f.stem) for f in files]
    for index, name in enumerate(names):
        print(index, name)
    try:
        index = int(input('please enter the index > '))
    except:
        log.info(f'need int from 0 to {len(names)-1}')
        return
    if 0 <= index < len(names):
        inkscape(files[index])
        maybe_recompile_figure(figure_path)
    else:
        # quit
        return

if __name__ == '__main__':
    cli()
