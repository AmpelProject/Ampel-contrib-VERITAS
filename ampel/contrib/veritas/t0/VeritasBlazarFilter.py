#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File              : ampel/contrib/veritas/t0/VeritasBlazarFilter.py
# License           : BSD-3-Clause
# Author            : m. nievas-rosillo <mireia.nievas-rosillo@desy.de>
# Date              : 06.09.2018
# Last Modified Date: 06.09.2018
# Last Modified By  : m. nievas-rosillo <mireia.nievas-rosillo@desy.de>

from numpy import exp, array
import logging
from urllib.parse import urlparse
from ampel.base.abstract.AbsAlertFilter import AbsAlertFilter

from pymongo import MongoClient
from extcats import CatalogQuery


class VeritasBlazarFilter(AbsAlertFilter):
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
		self.keys_to_check = ('ra', 'dec', 'rb')
		self.logger = logger if logger is not None else logging.getLogger()
		
		config_params = (
			'MIN_RB',					# real bogus score
			'MIN_MAG',					# brightness threshold [mag]
			'3FHL_RS_ARCSEC'			# search radius around 3FHL sources [arcsec]
			)
		for el in config_params:
			if el not in run_config:
				raise ValueError("Parameter %s missing, please check your channel config" % el)
			if run_config[el] is None:
				raise ValueError("Parameter %s is None, please check your channel config" % el)
			self.logger.info("Using %s=%s" % (el, run_config[el]))
		
		
		# ----- set filter proerties ----- #
		
		self.fhl3_rs_arcsec 			= run_config['3FHL_RS_ARCSEC']
		self.rb_th 						= run_config['MIN_RB']
		self.min_mag 					= run_config['MIN_MAG']

		# init the catalog query object for the 3fhl catalog
		catq_client = MongoClient(base_config['extcats.reader'])
		catq_kwargs = {'logger': self.logger, 'dbclient': catq_client}
		self.fhl3_query = CatalogQuery.CatalogQuery(
			"3FHL", ra_key='RAJ2000', dec_key='DEJ2000',
			logger=self.logger, dbclient=catq_client)


	def _alert_has_keys(self, photop):
		"""
			check that given photopoint contains all the keys needed to filter
		"""
		for el in self.keys_to_check:
			if el not in photop:
				self.logger.debug("rejected: '%s' missing" % el)
				return False
			if photop[el] is None:
				self.logger.debug("rejected: '%s' is None" % el)
				return False
		return True


	def apply(self, alert):
		"""
		Mandatory implementation.
		To exclude the alert, return *None*
		To accept it, either return
			* self.on_match_t2_units
			* or a custom combination of T2 unit names
		"""
		
		# cut on RB (1 is real, 0 is bogus)
		latest = alert.pps[0]
		if latest['rb'] < self.rb_th:
			self.logger.debug("rejected: RB score %.2f below threshod (%.2f)" %
				(latest['rb'], self.rb_th))
			return None

		# cut on magnitude
		if latest['magpsf'] > self.min_mag:
			self.logger.debug("rejected: magpsf %.2f above threshod (%.2f)" %
				(latest['magpsf'], self.min_mag))
			return None

		# check for positional coincidence with gamma-ray balazars
		if not self.fhl3_query.binaryserach(latest['ra'], latest['dec'], self.fhl3_rs_arcsec):
			self.logger.debug(
				"rejected: not within %.2f arcsec from any source in the 3FHL" % 
				(self.fhl3_rs_arcsec)
			)
			return None

		return self.on_match_t2_units

