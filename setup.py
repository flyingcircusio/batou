# This should be only one line. If it must be multi-line, indent the second
# line onwards to keep the PKG-INFO file format intact.
"""A utility for automating multi-host, multi-environment software builds and deployments.
"""

from setuptools import setup, find_packages
import glob
import os.path


def project_path(*names):
    return os.path.join(os.path.dirname(__file__), *names)


version = '0.2.8'

setup(
    name='batou',
    version=version,
    install_requires=[
        'Jinja2',
        'distribute',
        'mock',
        'paramiko>=1.8',
        'configobj',
        'zope.cachedescriptors',
    ],
    extras_require={
        'test': [
        ],
    },
    entry_points="""
        [console_scripts]
            batou-remote = batou.remote:main
            batou-local = batou.local:main
            secretsedit = batou.lib.secrets.edit:edit
    """,
    author='Christian Theune <ct@gocept.com>',
    author_email='ct@gocept.com',
    license='BSD (2-clause)',
    url='https://projects.gocept.com/projects/batou/',
    keywords='deployment',
    classifiers="""\
License :: OSI Approved :: BSD License
Programming Language :: Python
Programming Language :: Python :: 2
Programming Language :: Python :: 2.7
Programming Language :: Python :: 2 :: Only
"""[:-1].split('\n'),
    description=__doc__.strip(),
    long_description='\n\n'.join(open(project_path(name)).read() for name in (
            'README.txt',
            'CHANGES.txt',
            'HACKING.txt',
            )),

    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    data_files=[('', glob.glob(project_path('*.txt')))],
    zip_safe=False,
    test_suite='batou.tests',
)
