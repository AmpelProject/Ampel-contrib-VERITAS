
from setuptools import setup

setup(name='ampel-contrib-hu',
      version='0.4.1',
      packages=['ampel.contrib.hu',
                'ampel.contrib.hu.examples.t0',
                'ampel.contrib.hu.examples.t2',
                'ampel.contrib.hu.t0',
                'ampel.contrib.hu.t2',
                'ampel.contrib.hu.t3'],
      package_data = {'': ['*.json']},
      entry_points = {
          'ampel.channels' : [
              'hu = ampel.contrib.hu.channels:load_channels',
          ],
          'ampel.target_sources' : [
              'TargetSourceListener = ampel.contrib.hu.TargetSourceListener:TargetSourceListener',
          ],
          'ampel.pipeline.t2.configs' : [
              'hu = ampel.contrib.hu.channels:load_t2_run_configs',
          ],
          'ampel.pipeline.t0' : [
              'DecentFilter = ampel.contrib.hu.t0.DecentFilter:DecentFilter',
              'XShooterFilter = ampel.contrib.hu.t0.XShooterFilter:XShooterFilter',
              'LensedTransientFilter = ampel.contrib.hu.t0.LensedTransientFilter:LensedTransientFilter',
              'RandFilter = ampel.contrib.hu.t0.RandFilter:RandFilter',
              'ToOFilter = ampel.contrib.hu.t0.ToOFilter:ToOFilter',
              'SEDmTargetFilter = ampel.contrib.hu.t0.SEDmTargetFilter:SEDmTargetFilter',
              'NoFilter = ampel.contrib.hu.t0.NoFilter:NoFilter',
              'TransientInEllipticalFilter = ampel.contrib.hu.t0.TransientInEllipticalFilter:TransientInEllipticalFilter',
          ],
          'ampel.pipeline.t2.units' : [
              'SNCOSMO = ampel.contrib.hu.t2.T2SNCosmo:T2SNCosmo',
              'CATALOGMATCH = ampel.contrib.hu.t2.T2CatalogMatch:T2CatalogMatch',
              'POLYFIT = ampel.contrib.hu.examples.t2.T2ExamplePolyFit:T2ExamplePolyFit',
          ],
          'ampel.pipeline.t3.jobs' : [
              'hu = ampel.contrib.hu.channels:load_t3_jobs',
          ],
          'ampel.pipeline.t3.units' : [
              'TransientInfoPrinter = ampel.contrib.hu.t3.TransientInfoPrinter:TransientInfoPrinter',
              'TransientViewDumper = ampel.contrib.hu.t3.TransientViewDumper:TransientViewDumper',
              'TransientWebPublisher = ampel.contrib.hu.t3.TransientWebPublisher:TransientWebPublisher',
              'SlackSummaryPublisher = ampel.contrib.hu.t3.SlackSummaryPublisher:SlackSummaryPublisher',
              'MarshalPublisher = ampel.contrib.hu.t3.MarshalPublisher:MarshalPublisher',
          ],
          'ampel.pipeline.t3.configs' : [
              'hu = ampel.contrib.hu.channels:load_t3_run_configs',
          ],
          'ampel.pipeline.resources' : [
              'extcats = ampel.contrib.hu.resources:extcatsURI',
              'catsHTM = ampel.contrib.hu.resources:catsHTMPath',
              'desycloud = ampel.contrib.hu.resources:desyCloudURI',
          ]
      }
)
