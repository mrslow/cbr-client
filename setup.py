from setuptools import setup, find_packages

with open('README.md') as f:
    readme = f.read()

dependencies = ['httpx']

setup(
    name='cbr-client',
    version='0.1.3',
    description='Tool for easy working with https://portal5.cbr.ru API',
    long_description=readme,
    long_description_content_type="text/markdown",
    author='Anton Shchetikhin',
    author_email='animal2k@gmail.com',
    py_modules=['cbr_client'],
    install_requires=['httpx'],
    url='https://github.com/mrslow/cbr-client',
    keywords='cbr rest api client',
    packages=find_packages(),
    python_requires='>=3.7'
)
