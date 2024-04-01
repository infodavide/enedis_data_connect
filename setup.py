# -*- coding: utf-8 -*-
"""
Learn more: https://github.com/infodavide/enedis_data_connect
"""
import markdown # pip install markdown
from bs4 import BeautifulSoup
from setuptools import setup, find_packages

with open('README.md', encoding='utf-8') as f:
    html = markdown.markdown(f.read())
    soup = BeautifulSoup(html, features='html.parser')
    readme_content = soup.get_text()

with open('LICENSE', encoding='utf-8') as f:
    license_content = f.read()

setup(
    name='enedis_data_connect',
    version='1.0.0',
    description='Enedis data connect client',
    long_description=readme_content,
    author='David R', 
    author_email='contact@infodavid.org',
    url='https://github.com/infodavide/enedis_data_connect',
    license=license_content,
    packages=find_packages(exclude=('tests', 'docs'))
)

