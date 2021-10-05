# This should be only one line. If it must be multi-line, indent the second
# line onwards to keep the PKG-INFO file format intact.
"""A utility for automating multi-host, multi-environment software builds \
and deployments.
"""

from setuptools import find_packages, setup

version = open("src/batou/version.txt").read().strip()

setup(
    name="batou",
    version=version,
    install_requires=[
        "ConfigUpdater",
        "Jinja2",
        "requests",
        # ConfigUpdater does not manage its minimum requirements correctly.
        "setuptools>=38.3",
        "execnet>=1.8.1",
        "importlib_metadata",
        "py",
        "pyyaml",
        'remote-pdb', ],
    extras_require={
        "test": [
            "mock",
            "pytest",
            "pytest-coverage",
            "pytest-instafail",
            "pytest-timeout", ]},
    entry_points="""
        [console_scripts]
            batou = batou.main:main
        [zc.buildout]
            requirements = batou.buildout:Requirements
        [zest.releaser.prereleaser.after]
            update_requirements = batou.release:update_requirements
        [zest.releaser.postreleaser.after]
            update_requirements = batou.release:update_requirements
        [batou.provisioners]
            fc-nixos-dev-container = batou.provision:FCDevContainer
    """,
    author="Christian Theune",
    author_email="ct@flyingcircus.io",
    license="BSD (2-clause)",
    url="https://batou.readthedocs.io/en/latest/",
    keywords="deployment",
    classifiers="""\
License :: OSI Approved :: BSD License
Programming Language :: Python
Programming Language :: Python :: 3
Programming Language :: Python :: 3.6
Programming Language :: Python :: 3.7
Programming Language :: Python :: 3.8
Programming Language :: Python :: 3.9
Programming Language :: Python :: 3 :: Only
"""[:-1].split("\n"),
    description=__doc__.strip(),
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    packages=find_packages("src"),
    package_dir={"": "src"},
    include_package_data=True,
    zip_safe=False,
    test_suite="batou.tests",
    python_requires=">=3.6")
