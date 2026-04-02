from setuptools import setup
import os


def read(fname):
    try:
        return open(os.path.join(os.path.dirname(__file__), fname), encoding='utf-8').read()
    except FileNotFoundError:
        return "Interface for coupled simulation of power plant and geological storage."


setup(name='IF_PPlant_GeoStorage',
      version='0.1.1 dev',
      description='Interface for coupled simulation of power plant and geological energy storage',
      url='https://github.com/project-angus/IF_PPlant_GeoStorage',
      author='Wolf Tilmann Pfeiffer, Francesco Witt, Firdovsi Gasanzade',
      author_email='francesco.witte@hs-flensburg.de',
      long_description=read('README.rst'),
      license='GPL-3.0',
      packages=['coupled_simulation'],
      python_requires='>=3',
      install_requires=['TESPy >= 0.9.12',
                        'numpy >= 2.4.3',
                        'pandas >= 3.0.1'])
