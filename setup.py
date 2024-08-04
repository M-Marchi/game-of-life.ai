import pathlib
import sys

from setuptools import find_packages, setup

CURRENT_PYTHON_VERSION = sys.version_info[:2]
MIN_REQUIRED_PYTHON_VERSION = (3, 10)  # COMPATIBLE PYTHON VERSION
if CURRENT_PYTHON_VERSION < MIN_REQUIRED_PYTHON_VERSION:
    sys.stderr.write(
        """
==========================
Unsupported Python version
==========================
This version of isp_arepo requires Python {}.{}, but you're trying to
install it on Python {}.{}.
""".format(
            *(MIN_REQUIRED_PYTHON_VERSION + CURRENT_PYTHON_VERSION)
        )
    )
    sys.exit(1)

requirements = (
    (pathlib.Path(__file__).parent / "requirements.txt").read_text().splitlines()
)

EXCLUDE_FROM_PACKAGES = []

setup(
    name="game-of-life",
    version="0.0.1",
    python_requires=">={}.{}".format(*MIN_REQUIRED_PYTHON_VERSION),
    url="",
    author="",
    author_email="",
    description=(""),
    license="",
    packages=find_packages(exclude=EXCLUDE_FROM_PACKAGES),
    include_package_data=True,
    install_requires=requirements,
    entry_points={},
    zip_safe=False,
)
