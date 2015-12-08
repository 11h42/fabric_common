import glob
import os
from datetime import datetime
from subprocess import check_call

# noinspection PyPackageRequirements
from fabric.api import env, lcd, cd, run, put, settings, prefix, task, get
# noinspection PyPackageRequirements
from fabric.contrib.project import rsync_project

__author__ = 'Cedric RICARD'
__all__ = ['start', 'stop', 'empty_folder', 'deploy', 'deploy_app', 'dump_db', 'load_db',
           'make_archive',
           'create_superuser', 'load_initial_data',
           'install_system',
           ]


@task
def stop():
    run("supervisorctl stop %s" % env.app_name)


@task
def start():
    run("supervisorctl start %s" % env.app_name)


def _run_compile(folder_list=None, clear=False, all_libraries=True):
    with cd(env.app_dir):
        put(os.path.join(os.path.dirname(__file__), 'compile.py'), remote_path=env.app_dir)
        if clear:
            run("python -O compile.py -c")
        elif folder_list is not None:
            run("python -O compile.py %s %s" % (
                all_libraries and '-a' or '',
                ' '.join(map(lambda x: '"%s"' % x, folder_list))
            ))
        run('rm compile.py')


def compile_python_files():
    _run_compile(env.app_folder_list)


def clean_compiled_files():
    # cleanup *.pyc / *.pyo files
    _run_compile(clear=True)


def sync_sources(test_only=False):
    rsync_project(
        env.app_dir,
        local_dir=env.local_dir + "/",
        delete=True,
        default_opts='-thrvz',
        extra_opts='-ci --filter=". %s"' % env.rsync_filter + (test_only and " --dry-run" or ""),
    )


@task
def empty_folder():
    with settings(warn_only=True):
        with cd(env.app_dir):
            run('find . -type f -name \'*.tar.gz\' | xargs rm -rf')
            run('rm -r %s' % ' '.join(map(lambda x: '"%s"' % x, env.app_folder_list)))


@task
def make_archive():
    """
    Very simple task that make an archive from the application folder list and other files list
    """
    fname = 'build-%s-%s.tar.gz' % (env.app_name, datetime.now().strftime("%Y-%m-%dT%H-%M-%S"))
    with lcd(env.local_dir):
        args = ['tar', '-czf', fname]
        args.extend(env.app_folder_list)
        args.extend(env.app_other_files_list)

        check_call(args, cwd=env.local_dir)
    print("Archive created: %s" % fname)
    return fname


def untar_archive():
    tar_gz_build_files = glob.glob(os.path.join(env.local_dir, 'build-%s-*.tar.gz' % env.app_name))
    if not len(tar_gz_build_files):
        raise IOError("Can't find Archive!")
    tar_gz_build_file = tar_gz_build_files[-1]
    tar_gz_file_name = tar_gz_build_file.split(os.path.sep)[-1]

    with cd(env.app_dir):
        put(tar_gz_build_file, env.app_dir)
        run('tar -xzvf ' + tar_gz_file_name)


@task
def deploy_app(with_rsync=True):
    run("mkdir -p %s" % env.app_dir)
    if with_rsync:
        sync_sources()
    else:
        empty_folder()
        untar_archive()
    clean_compiled_files()
    # compile_python_files()

    with cd(env.app_dir):
        with settings(warn_only=True):
            if run("test -d .env").failed:
                run("virtualenv .env")

        if 'static_dir' in env:
            run('rm -rf %s' % env.static_dir)
        with prefix('. %s/.env/bin/activate' % env.app_dir):
            run('pip install -r requirements.txt --upgrade')
            with cd(env.django_app_dir):
                run('python manage.py migrate --noinput')
                if 'static_dir' in env:
                    run('python manage.py collectstatic --noinput')

        run('chown -R %s:%s .' % (env.app_user, env.app_user))


@task
def load_initial_data(fixture_path):
    with cd(env.app_dir):
        with prefix('. %s/.env/bin/activate' % env.app_dir):
            with cd(env.django_app_dir):
                run("python ./manage.py loaddata %s" % fixture_path)
                run('python manage.py createsuperuser')


@task
def create_superuser():
    with cd(env.app_dir):
        with prefix('. %s/.env/bin/activate' % env.app_dir):
            with cd(env.django_app_dir):
                run('python manage.py createsuperuser')


def rsync_deploy():
    stop()
    deploy_app(with_rsync=True)
    start()


@task(default=True)
def deploy():
    stop()
    make_archive()
    deploy_app(with_rsync=False)
    start()


@task
def dump_db():
    with cd(env.app_dir):
        with prefix('. %s/.env/bin/activate' % env.app_dir):
            with cd(env.django_app_dir):
                fname = 'dump-%s.json' % datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
                run('python manage.py dumpdata > %s' % fname)
                get(fname)


@task
def load_db(fname):
    if os.path.exists(fname):
        with cd(env.app_dir):
            with prefix('. %s/.env/bin/activate' % env.app_dir):
                with cd(env.django_app_dir):
                    put(fname)
                    run('python manage.py loaddata %s' % fname)


@task
def install_system():
    with lcd(env.fab_dir):
        args = ['ansible-playbook', '--ask-sudo-pass', '-i', "%s:%s," % (env.host, env.port), '%s.yml' % env.app_name]
        check_call(args, cwd=env.fab_dir, shell=False)