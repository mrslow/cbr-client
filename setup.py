from setuptools import find_packages, setup

with open("README.md") as f:
    readme = f.read()

dependencies = ["httpx", "pydantic"]

setup(
    name="cbr-client",
    version="0.4.0",
    description="Tool for easy working with https://portal5.cbr.ru API",
    long_description=readme,
    long_description_content_type="text/markdown",
    author="Anton Shchetikhin",
    author_email="animal2k@gmail.com",
    license="MIT",
    license_file="LICENSE",
    py_modules=["cbr_client"],
    install_requires=["httpx", "pydantic"],
    url="https://github.com/mrslow/cbr-client",
    keywords="cbr rest api client",
    packages=find_packages(),
    python_requires=">=3.7",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
)
