#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File              : ampel/contrib/hu/TargetCatalogIngester.py
# License           : BSD-3-Clause
# Author            : m. giomi <matteo.giomi@desy.de>
# Date              : 19.06.2018
# Last Modified Date: 19.06.2018
# Last Modified By  : Jakob van Santen <jakob.van.santen@desy.de>

import logging, json
from astropy import units as u
from astropy.time import Time
from pymongo import MongoClient, GEOSPHERE

log = logging.getLogger(__name__)

class TargetCatalogIngester:
	"""
	Client for inserting new targets in a search catalog
	"""
	@u.quantity_input
	def __init__(self, mongo_uri, db_name, collection_name, maximum_radius: 'angle'):
		"""
		:param mongo_uri: URI for MongoClient connection
		:param db_name: Name of ToO target database
		:param collection_name: Name of collection for the target program
		:param maximum_radius: maximum positional uncertainty for targets in
		    this program. Inserting a target with a larger positional uncertainty
		    will raise an error.
		"""
		db = MongoClient(mongo_uri).get_database(db_name)
		meta = db.get_collection("meta")
		entry = {
			"_id" : "pos",
			"key" : "pos",
			"is_indexed" : 'true',
			"pos_format" : "geoJSON",
			"type" : "sphere2d"
		}
		meta.update_one({}, {'$set': entry}, upsert=True)
		self.collection = db.get_collection(collection_name)
		self.collection.create_index([('pos', GEOSPHERE)])
		self._maximum_radius = maximum_radius

	@u.quantity_input
	def add_target(self, ra : 'angle', dec : 'angle', radius : 'angle', start, end, extras={}):
		"""
		Add a new target to the search list
		
		:param ra: right ascension (J2000)
		:param dec: declination (J2000)
		:param radius: uncertainty of source position (circularized)
		:param start: start date of search period
		:param end: end date of search period
		:param extras: extra items to be included in the target document
		
		"""
		if radius > self._maximum_radius:
			raise ValueError("Error circle ({}) is larger than maximum search radius ({})".format(radius, self._maximum_radius))
		doc = {
			'ra': ra.to(u.deg).value,
			'dec': dec.to(u.deg).value,
			'r68': radius.to(u.arcsec).value,
			'jd_min': Time(start).jd,
			'jd_max': Time(end).jd,
			**extras
		}
		self.add_geojson_key(doc)

		self.collection.insert_one(doc)
		log.debug("Inserted target document:\n%s"%repr(doc))

	@staticmethod
	def add_geojson_key(doc):
		# geoJSON needs longitude between -180 and +180
		ra=doc['ra'] if doc['ra']<180. else doc['ra']-360.
		doc['pos']={
			'type': 'Point', 
			'coordinates': [ra, doc['dec']]
		}
