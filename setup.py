from setuptools import setup, find_packages
import os

def read_requirements(filename):
    base_path = os.path.dirname(__file__)
    requirements_path = os.path.join(base_path, filename)

    with open(requirements_path) as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]

def wrap_find_packages():
    r = find_packages()
    for p in find_packages(where="./captaincredz/plugins"):
        r.append(f"captaincredz.plugins.{p}")
    for p in find_packages(where="./captaincredz/post_actions"):
        r.append(f"captaincredz.post_actions.{p}")
    return r

def find_extras():
    d = dict()
    d['progressbar'] = read_requirements('optional-requirements.txt')
    for p in os.listdir('captaincredz/plugins'):
        p_req = os.path.join("captaincredz/plugins", p, "requirements.txt")
        if os.path.isfile(p_req):
            d[p] = read_requirements(p_req)
    for pa in os.listdir('captaincredz/post_actions'):
        pa_req = os.path.join("captaincredz/post_actions", pa, "requirements.txt")
        if os.path.isfile(pa_req):
            d[pa] = read_requirements(pa_req)
    return d

with open("/tmp/a", "w+") as f:
    f.write(str(wrap_find_packages()))

setup(
    name='captaincredz',
    version='1.0.0',
    install_requires=read_requirements('requirements.txt'),
    py_modules=['captaincredz'],
    packages=wrap_find_packages(),
    extras_require=find_extras(),
    entry_points={
        'console_scripts': [
            'captaincredz=captaincredz:main',
        ],
    },
    author='Antoine Gicquel',
    author_email='antoine.gicquel@synacktiv.com',
    description='CaptainCredz is a powerful password spraying utility.',
)
