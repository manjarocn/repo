#!/usr/bin/python3

import os
import sys
import re
import subprocess
from pathlib import Path


def prin(*args, error=False, **kwargs):
    print(':point_right: ManjaroCN --->', *args,
          file=sys.stderr if error else sys.stdout, **kwargs)


def parse_env():
    shell = os.environ.get('SHELL', '/bin/bash')
    branch = os.environ.get('BRANCH', 'stable')
    image = os.environ.get('IMAGE', 'manjarocn/base:%s-latest' % branch)
    makeflags = os.environ.get('MAKEFLAGS', '-j%d' % (os.cpu_count() + 1))
    paths = {
        'ARCHCN': ['../archlinuxcn_repo/archlinuxcn', '/build/workspace'],
        'GPGDIR': ['~/.gnupg', '/gpg'],
        'PKGCACHE': ['../pkgcache', '/pkgcache'],
        'PKGDEST': ['../build/packages', '/build/packages'],
        'SRCDEST': ['../build/sources', '/build/sources'],
        'SRCPKGDEST': ['../build/srcpackages', '/build/srcpackages'],
    }

    for k, v in paths.items():
        v[0] = os.environ.get(k, v[0])
        v[0] = Path(v[0]).expanduser().resolve()
        if not v[0].is_dir():
            if k in ['ARCHCN', 'GPGDIR']:
                raise FileNotFoundError(v[0])
            v[0].mkdir(0o755, True, True)

    return {
        'shell': shell,
        'branch': branch,
        'image': image,
        'makeflags': makeflags,
        'paths': paths,
    }


def build(pkg, env, errors, depth=0):
    pkgbuild = env['paths']['ARCHCN'][0] / pkg / 'PKGBUILD'
    if not pkgbuild.is_file():
        errors.append([pkg, 'PKGBUILD not found'])
        return False

    if depth > 10:
        errors.append([pkg, 'depends too deep'])
        prin('Build %s failed:' % pkg, 'depends too deep', error=True)
        return False

    depends = subprocess.run([
        env['shell'], '-c',
        'source %s; echo -n "${depends[@]}"; echo -n " ${makedepends[@]}"' % pkgbuild.as_posix(),
    ], stdout=subprocess.PIPE)
    depends = [re.split('>|=|<', i)[0] for i in depends.stdout.decode('utf8').split()]
    depends = [i for i in depends if (env['paths']['ARCHCN'][0] / i).is_dir()]
    if depends:
        prin('Found depends:', depends)
        for i in depends:
            if not build(i, env, errors, depth + 1):
                prin('Build a depend %s of %s failed:' % (i, pkg), error=True)
                return False

    cmd = ['docker', 'run', '--rm', '-e', 'MAKEFLAGS=' + env['makeflags']]
    for k, v in env['paths'].items():
        cmd.extend(['-v', '%s:%s:%s' % (
            v[0] if k != 'ARCHCN' else env['paths']['ARCHCN'][0] / pkg,
            v[1],
            'rw' if k != 'GPGDIR' else 'ro',
        )])
    cmd.append(env['image'])
    prin('Building %s:' % pkg, cmd)

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        errors.append([pkg, e])
        prin('Build %s failed:' % pkg, e, error=True)
        return False

    return True


def main():
    env = parse_env()
    prin('Build env vars:', env)

    errors = []
    with (Path(__file__).parent / 'list.txt').open(encoding='utf8') as f:
        for i in f:
            i = env['paths']['ARCHCN'][0].glob(i.strip())
            for j in i:
                build(j.name, env, errors)

    if errors:
        prin('Build errors:', error=True)
        for e in errors:
            prin(e[0], e[1], error=True)


if __name__ == '__main__':
    main()