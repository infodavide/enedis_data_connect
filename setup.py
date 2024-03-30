# -*- coding: utf-8 -*-
# Learn more: https://github.com/infodavide/enedis_data_connect/setup.py
from setuptools import setup, find_packages

with open('README.md') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

setup(
    name='enedis_data_connect',
    version='1.0.0',
    description='Enedis data connect client',
    long_description=readme,
    author='David Rolland',
    author_email='contact@infodavid.org',
    url='https://github.com/infodavide/enedis_data_connect',
    license=license,
    packages=find_packages(exclude=('tests', 'docs'))
)

