# This should be only one line. If it must be multi-line, indent the second
# line onwards to keep the PKG-INFO file format intact.
"""A utility for automating multi-host, multi-environment software builds \
and deployments.
"""

from setuptools import setup, find_packages
import glob
import os.path


def project_path(*names):
    return os.path.join(os.path.dirname(__file__), *names)


version = open('src/batou/version.txt').read().strip()

setup(
    name='batou',
    version=version,
    install_requires=[
        'Jinja2',
        'requests',
        'setuptools',
        'execnet',
        'py'
    ],
    extras_require={
        'test': [
        ],
    },
    entry_points="""
        [console_scripts]
            batou-init = batou.init:console_main
        [zc.buildout]
            requirements = batou.buildout:Requirements
        [zest.releaser.prereleaser.after]
            update_requirements = batou.release:update_requirements
        [zest.releaser.postreleaser.after]
            update_requirements = batou.release:update_requirements
    """,
    author='Christian Theune',
    author_email='ct@flyingcircus.io',
    license='BSD (2-clause)',
    url='https://plan.flyingcircus.io/projects/batou',
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
            'README',
            'CHANGES.txt',
            )),

    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    data_files=[('', glob.glob(project_path('*.txt')))],
    zip_safe=False,
    test_suite='batou.tests',
)
