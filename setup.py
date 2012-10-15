# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

# This should be only one line. If it must be multi-line, indent the second
# line onwards to keep the PKG-INFO file format intact.
"""A utility for automating multi-host, multi-environment software builds and deployments.
"""

from setuptools import setup, find_packages
import glob
import os.path


def project_path(*names):
    return os.path.join(os.path.dirname(__file__), *names)


version = '0.1.3'

setup(
    name='batou',
    version=version,
    install_requires=[
        'distribute',
        'Fabric',
        'Mako',
        'Jinja2',
        'mock',
    ],
    extras_require={
        'test': [
        ],
    },
    entry_points="""
        [console_scripts]
            batou-remote = batou.remote:main
            batou-local = batou.local:main
            secretsedit = batou.secrets:edit
    """,
    author='gocept <mail@gocept.com>',
    author_email='mail@gocept.com',
    license='ZPL',
    url='https://projects.gocept.com/projects/batou/',
    keywords='deployment',
    classifiers="""\
License :: OSI Approved :: Zope Public License
Programming Language :: Python
Programming Language :: Python :: 2
Programming Language :: Python :: 2.6
Programming Language :: Python :: 2.7
Programming Language :: Python :: 2 :: Only
"""[:-1].split('\n'),
    description=__doc__.strip(),
    long_description='\n\n'.join(open(project_path(name)).read() for name in (
            'README.txt',
            'HACKING.txt',
            'CHANGES.txt',
            )),

    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    data_files=[('', glob.glob(project_path('*.txt')))],
    zip_safe=False,
    test_suite='batou.tests',
)
