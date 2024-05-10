Google Patents Scraper
======================

Installation
------------

You can install this package directly from GitHub with the following:

.. code:: shell

   pip install git+https://github.com/dhrosa/google-patents-scraper.git

If you have this repository downloaded locally, you can install it from its directory using:

.. code:: shell

   pip install .

Usage
-----

Once installed, run the command using something like the following:

.. code:: shell

   google-patents-scraper KR101863193B1 > out.json

Or the following if pip-installed packages are not in your ``PATH``:

.. code:: shell

   python3 -m google_patents_scraper.main KR101863193B1 > out.json
