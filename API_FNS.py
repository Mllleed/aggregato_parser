from setuptools import setup, find_packages


APP_NAME = 'parser'
VERSION = '1.0.0'
AUTHOR = 'Эдя'
DESCRIPTION = 'помилуйте парсер, ему очень плохо'

# Список зависимостей
with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name=APP_NAME,
    version=VERSION,
    author=AUTHOR,
    description=DESCRIPTION,
    packages=find_packages(),
    install_requires=requirements,
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'myapp=src.main:main',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: MacOS',
        'Operating System :: POSIX :: Linux',
    ],
)