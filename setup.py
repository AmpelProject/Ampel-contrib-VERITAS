
from setuptools import setup

setup(name='ampel-contrib-veritas',
      version='0.5.0',
      packages=['ampel.contrib.veritas',
                'ampel.contrib.veritas.t0',
                'ampel.contrib.veritas.t2'],
                #'ampel.contrib.veritas.t3'],
      package_data = {'': ['*.json']},
      entry_points = {
          'ampel.channels' : [
              'veritas = ampel.contrib.veritas.channels:load_channels',
          ],
          'ampel.t2.configs' : [
              'veritas = ampel.contrib.veritas.channels:load_t2_run_configs',
          ],
          'ampel.t0.units' : [
              'VeritasBlazarFilter = ampel.contrib.veritas.t0.VeritasBlazarFilter:VeritasBlazarFilter'
          ],
          'ampel.t2.units' : [
              #'CATALOGMATCH = ampel.contrib.veritas.t2.T2CatalogMatch:T2CatalogMatch'
              'T2BLAZARPRODUTCS = ampel.contrib.veritas.t2.T2BlazarProducts:T2BlazarProducts'
          ],
          #'ampel.t3.jobs' : [
          #    'veritas = ampel.contrib.veritas.channels:load_t3_jobs',
          #],
          #'ampel.resources' : [
          #    'extcats = ampel.contrib.veritas.resources:extcatsURI',
          #]
      }
)
