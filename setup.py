
from setuptools import setup

setup(name='ampel-contrib-veritas',
      version='0.4.1',
      packages=['ampel.contrib.veritas',
                'ampel.contrib.veritas.t0'],
      package_data = {'': ['*.json']},
      entry_points = {
          'ampel.channels' : [
              'hu = ampel.contrib.veritas.channels:load_channels',
          ],
          'ampel.pipeline.t2.configs' : [
              'hu = ampel.contrib.veritas.channels:load_t2_run_configs',
          ],
          'ampel.pipeline.t0' : [
              'VeritasBlazarFilter = ampel.contrib.veritas.t0.VeritasBlazarFilter:VeritasBlazarFilter'
          ],
          'ampel.pipeline.t3.jobs' : [
              'hu = ampel.contrib.veritas.channels:load_t3_jobs',
          ],
          'ampel.pipeline.t3.configs' : [
              'hu = ampel.contrib.veritas.channels:load_t3_run_configs',
          ],
          'ampel.pipeline.resources' : [
              'extcats = ampel.contrib.hu.resources:extcatsURI'
          ]
      }
)
