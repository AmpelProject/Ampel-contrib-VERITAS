
from ampel.core.abstract.AbsTargetSource import AbsTargetSource
from ampel.contrib.hu.TargetCatalogIngester import TargetCatalogIngester

from astropy import units as u
from astropy.time import Time
from datetime import datetime
import pymongo
import asyncio

class TargetSourceListener(AbsTargetSource):
	"""
	Listen for new sources on a socket
	
	Feed with e.g.: echo '141 45 2.5 2018-06-22T12:00:00 2018-06-23T12:00:00 NO_FILTER' | nc localhost 12345
	"""
	
	version = 0.1
	
	resources = ('extcats.writer',)
	def __init__(self, base_config=None, run_config=None):
		self._queue = asyncio.Queue(maxsize=0)
		
		# TODO: generalize run config
		run_config = {'ToOTargetCollection': 'test', 'InclusiveSearchRadius': 60.0}
		self.ingester = TargetCatalogIngester(base_config['extcats.writer'],
		    "ToO",
		    run_config['ToOTargetCollection'],
		    run_config['InclusiveSearchRadius']*u.arcsec
		)

	async def handle_connection(self, reader, writer):
		line = await reader.readline()
		try:
			fields = line.decode().strip().split(' ')
			if len(fields) < 6:
				raise ValueError('Too few fields')
			ra, dec, radius = map(lambda s: float(s)*u.deg, fields[:3])
			jd_min, jd_max = map(Time, fields[3:5])
			channels = fields[5:]
			self.ingester.add_target(ra, dec, radius, jd_min, jd_max, {'source': 'TargetSourceListener', 'inserted': datetime.utcnow()})
			target = ((ra, dec), radius, (jd_min, jd_max), channels)
			await self._queue.put(target)
			writer.write('{}\n'.format(target).encode())
		except Exception as e:
			writer.write((str(e)+'\n').encode())
		finally:
			await writer.drain()
			writer.close()

	async def get_targets(self):
		import sys
		sys.stderr.write('going to start\n')
		server = await asyncio.start_server(self.handle_connection, '127.0.0.1', 12345)
		while True:
			yield await self._queue.get()
		
		server.close()
		await server.wait_closed()
