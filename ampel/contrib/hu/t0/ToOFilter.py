#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File              : ampel/contrib/hu/t0/ToOFilter.py
# License           : BSD-3-Clause
# Author            : m. giomi <matteo.giomi@desy.de>
# Date              : 18.06.2018

import logging
from pymongo import MongoClient
from urllib.parse import urlparse
from ampel.base.abstract.AbsAlertFilter import AbsAlertFilter
from extcats.catquery_utils import searcharound_2Dsphere, get_distances

class ToOFilter(AbsAlertFilter):
	"""
	"""

	# Static version info
	version = 1.0
	resources = ('extcats.reader',)

	def __init__(self, on_match_t2_units, base_config=None, run_config=None, logger=None):
		"""
		"""
		if run_config is None or len(run_config) == 0:
			raise ValueError("Please check you run configuration")

		self.on_match_t2_units = on_match_t2_units
		self.logger = logger if logger is not None else logging.getLogger()
		
		# --------------------------------------------------------------------- #
		#																		#
		#						PARSE CONFIG PARAMETERS							#
		#																		#
		# ----------------------------------------------------------------------#
		config_params = (
						'ToOTargetDatabase',
						'ToOTargetCollection',
						'Sphere2DKey',
						'InclusiveSearchRadius',
						'TargetRAKey',
						'TargetDecKey',
						'TargetMinJDKey',
						'TargetMaxJDKey',
						'TargetErrRadKey'
						)
		for el in config_params:
			if el not in run_config:
				raise ValueError("Parameter %s missing, please check your channel config" % el)
			if run_config[el] is None:
				raise ValueError("Parameter %s is None, please check your channel config" % el)
			self.logger.info("Using %s=%s" % (el, run_config[el]))

		# target database and collection
		self.target_db							= run_config['ToOTargetDatabase']
		self.collection_name					= run_config['ToOTargetCollection']
		# query parameters
		self.sphere2d_key						= run_config['Sphere2DKey']
		self.inclusive_rs						= run_config['InclusiveSearchRadius']
		# schema of too targets
		self.target_ra_key						= run_config['TargetRAKey']
		self.target_dec_key						= run_config['TargetDecKey']
		self.target_jdmin_key					= run_config['TargetMinJDKey']
		self.target_jdmax_key					= run_config['TargetMaxJDKey']
		self.taget_err_rad_key					= run_config['TargetErrRadKey']
		
		
		# --------------------------------------------------------------------- #
		#																		#
		#						CONNECT TO TARGET DATABASE						#
		#																		#
		# ----------------------------------------------------------------------#
		
		self.db_client = MongoClient(base_config['extcats.reader'])
		self.target_coll = self.db_client[self.target_db][self.collection_name]
		self.logger.info("using mongo client at {}".format(self.db_client.address))
		self.logger.info("connected to collection %s of database %s."%
			(self.target_coll.name, self.target_db))


	def inspect_nearby_targets(self, alert_ra, alert_dec, nearby_targets):
		"""
			look at the separation between the alert position and each of the
			sources in the nearby_target_table.
		"""
		
		# compute distances of too targets to alert position (in arcsec)
		dists = get_distances(
			alert_ra, 
			alert_dec,
			nearby_targets, 
			self.target_ra_key, 
			self.target_dec_key)
		nearby_targets['d2target'] = dists
		
		# check if one nearby taget is closer than its error radius
		matches = dists<nearby_targets[self.taget_err_rad_key]
		if any(matches):
			return nearby_targets[matches]
		else:
			return None

	def apply(self, alert):
		"""
		Mandatory implementation.
		To exclude the alert, return *None*
		To accept it, either return
			* self.on_match_t2_units
			* or a custom combination of T2 unit names
		"""
		
		
		# if too target collection is empty reject
		if self.target_coll.find_one() is None:
			self.logger.debug("no targets in collection %s. rejecting."%self.collection_name)
			return None
		self.logger.debug("found %d targets in collection %s. Taking a look"%
			(self.target_coll.count(), self.collection_name))
		
		# get position and time of latest detction for alert
		latest = alert.pps[0]
		alert_ra, alert_dec, alert_jd =  latest['ra'], latest['dec'], latest['jd']	# TODO: do we need start of alert history?
		
		# find all ToO targets that are within a large search radius 
		# from alert position. This returns and astropy Table
		nearby_targets = searcharound_2Dsphere(
								alert_ra, 
								alert_dec, 
								rs_arcsec=self.inclusive_rs,
								src_coll=self.target_coll, 
								s2d_key=self.sphere2d_key,
								find_one=False, 
								logger=self.logger)
		if nearby_targets is None:
			self.logger.debug("no targets in collection %s within %.2f arsec. rejecting."%(self.collection_name, self.inclusive_rs))
			return None
		self.logger.debug("found %d too tagets within %.2f arcsec from alert position."
			%(len(nearby_targets), self.inclusive_rs))
		self.logger.debug(nearby_targets)
		
		# check that the inclusive search radius is indeed big enough 
		# TODO: that's a weak check since you don't look in the full collection.
		if any(nearby_targets[self.taget_err_rad_key]>self.inclusive_rs):
			raise RuntimeError("found target with positional uncertainty greater than conservative assumption.")
		
		# now look if any of this nearby targets is actually close enough
		found = self.inspect_nearby_targets(alert_ra, alert_dec, nearby_targets)
		if found is None:
			self.logger.debug("No target compatible with alert position.")
			return None
		else:
			self.logger.info("This alert is compatible with ToO target(s):")
			self.logger.info(found[['_id', self.target_ra_key, self.target_dec_key, 'd2target']])
			return self.on_match_t2_units
