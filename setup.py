
from setuptools import setup

setup(
    author='Simon Woerner',
    author_email='git@simon-woerner.de',
    description='Parse and generate Content-Disposition headers',
    url='https://github.com/SWW13/python-rfc6266-parser',
    keywords='rfc6266 parser Content-Disposition http attachments',
    name='rfc6266-parser',
    version='0.0.5-2',  # semver
    license='GNU LGPL',
    platforms='OS-independent',
    py_modules=['rfc6266_parser', 'test_rfc6266_parser'],
    install_requires=['LEPL'],
    use_2to3=True,
    long_description=open('README').read(),
    classifiers=(
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)',
        'Topic :: Internet :: WWW/HTTP',
    ),
)

