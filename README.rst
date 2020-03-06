========
Overview
========

.. start-badges

.. list-table::
    :stub-columns: 1

    * - docs
      - |docs|
    * - tests
      - |
        |
    * - package
      - | |version| |wheel| |supported-versions| |supported-implementations|
        | |commits-since|
.. |docs| image:: https://readthedocs.org/projects/zencelium/badge/?style=flat
    :target: https://readthedocs.org/projects/zencelium
    :alt: Documentation Status

.. |version| image:: https://img.shields.io/pypi/v/zencelium.svg
    :alt: PyPI Package latest release
    :target: https://pypi.org/project/zencelium

.. |wheel| image:: https://img.shields.io/pypi/wheel/zencelium.svg
    :alt: PyPI Wheel
    :target: https://pypi.org/project/zencelium

.. |supported-versions| image:: https://img.shields.io/pypi/pyversions/zencelium.svg
    :alt: Supported versions
    :target: https://pypi.org/project/zencelium

.. |supported-implementations| image:: https://img.shields.io/pypi/implementation/zencelium.svg
    :alt: Supported implementations
    :target: https://pypi.org/project/zencelium

.. |commits-since| image:: https://img.shields.io/github/commits-since/zentropi/python-zencelium/v2020.0.1.svg
    :alt: Commits since latest release
    :target: https://github.com/zentropi/python-zencelium/compare/v2020.0.1...master



.. end-badges

Zencelium: Personal Zentropi Instance Server

* Free software: BSD 3-Clause License

Installation
============

::

    pip install zencelium

You can also install the in-development version with::

    pip install https://github.com/zentropi/python-zencelium/archive/master.zip


Documentation
=============


https://zencelium.readthedocs.io/


Development
===========

To run the all tests run::

    tox

Note, to combine the coverage data from all the tox environments run:

.. list-table::
    :widths: 10 90
    :stub-columns: 1

    - - Windows
      - ::

            set PYTEST_ADDOPTS=--cov-append
            tox

    - - Other
      - ::

            PYTEST_ADDOPTS=--cov-append tox
