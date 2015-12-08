import os
import py_compile
import re
import sys
from os.path import join

verbose = '-v' in sys.argv
delete_py = '--delete-py' in sys.argv
excludes = []  # don't visit .svn directories
exclude = re.compile("(/[.]svn)|(/nolimit)|(/commands)|(settings.py)")


def clean_pyc_files(base_dir):
    for root, dirs, files in os.walk(base_dir):
        for name in files:
            if name.endswith(".pyc") or name.endswith(".pyo"):
                fullpath = join(root, name)
                print("Deleting '%s'... " % fullpath),
                os.remove(fullpath)
                print("Ok")
        for name in ('.svn', '.git', '.hg'):
            if name in dirs:
                dirs.remove(name)  # don't visit .svn, .git and .hg directories


def compile_python(base_dir):
    _errors = []
    for root, dirs, files in os.walk(base_dir):
        for name in files:
            if name.endswith(".py"):
                fullpath = join(root, name).replace('\\', '/')
                if exclude.search(fullpath):
                    continue
                if verbose:
                    print("Compiling '%s'... " % fullpath),
                # noinspection PyBroadException
                try:
                    py_compile.compile(fullpath)
                    if delete_py:
                        os.remove(fullpath)
                    if verbose:
                        print("Ok")
                except Exception:
                    if verbose:
                        print("ERROR: %s" % str(Exception))
                    sys.stderr.write("ERROR compiling '%s': %s\n" % (fullpath, str(Exception)))
                    _errors.append((fullpath, Exception))
        for d in excludes:
            if d in dirs:
                dirs.remove(d)
    return _errors


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description='Utilities to compile Python source files.')
    parser.add_argument('-c', action='store_true', dest='clear',
                        help="removing all .pyc files")
    parser.add_argument('-a', action='store_true', dest='all',
                        help='compile also all installed python packages. ')
    parser.add_argument('folders', metavar='dir', nargs='*',
                        help='application folder to compile')

    args = parser.parse_args()

    base_dirs = args.folders
    if args.clear:
        print("Removing all .pyc files...")
        for dir_name in base_dirs:
            clean_pyc_files(dir_name)
    else:
        errors = []
        for dir_name in base_dirs:
            errors.append(compile_python(dir_name))
        print()
        if len(errors):
            sys.stderr.write("%d error(s) found!\n" % len(errors))
        else:
            print("Application's files successfully compiled!")

        if args.all:
            import compileall

            print("Compiling Python Libraries...")
            compileall.compile_path(True, 10)

        print("Finished!")
