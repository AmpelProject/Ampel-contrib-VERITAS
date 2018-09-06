#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File              : ampel/contrib/hu/t3/TransientInfoPrinter.py
# License           : BSD-3-Clause
# Author            : vb <vbrinnel@physik.hu-berlin.de>
# Date              : 11.06.2018
# Last Modified Date: 04.09.2018
# Last Modified By  : vb <vbrinnel@physik.hu-berlin.de>

from ampel.pipeline.common.ZTFUtils import ZTFUtils
from ampel.base.flags.TransientFlags import TransientFlags
from ampel.base.TransientView import TransientView
from ampel.base.abstract.AbsT3Unit import AbsT3Unit

class TransientInfoPrinter(AbsT3Unit):
	"""
	"""

	version = 0.1


	def __init__(self, logger, run_config=None, base_config=None, global_info=None):
		"""
		"""
		self.logger = logger
		self.count = 0
		self.printed_ids = []

		if global_info is not None:
			self.logger.info("Provided global info: %s" % global_info)


	def add(self, transients):
		"""
		"""
		if transients is not None:

			batch_count = len(transients)
			self.logger.info("Printing info of %i transient(s)" % batch_count)
			self.count += batch_count

			for tran_view in transients:
				TransientInfoPrinter._print_info(tran_view, self.logger)
				self.logger.info("-")
				self.printed_ids.append(tran_view.tran_id)

		else:
			self.logger.info("No transient provided")


	def done(self):
		"""
		"""
		self.logger.info("Total number of transient printed: %i" % self.count)
		return self.printed_ids


	@staticmethod
	def _print_info(tran, logger):
		""" 
		"""
		logger.info(" -> Ampel ID: %i" % tran.tran_id)

		# pylint: disable=no-member
		if TransientFlags.INST_ZTF in tran.flags:
			logger.info(" -> ZTF ID: %s" % ZTFUtils.to_ztf_id(tran.tran_id))

		if tran.channel is not None:
			logger.info(" -> Channel: %s" % str(tran.channel))

		created = tran.get_time_created(True)
		modified = tran.get_time_modified(True)
		logger.info(" -> Created: %s" % (created if created is not None else 'Not available'))
		logger.info(" -> Modified: %s" % (modified if modified is not None else 'Not available'))
		logger.info(" -> Flags: %s" % (tran.flags if tran.flags is not None else "Not set"))
		logger.info(" -> Latest state: %s" % (
			tran.latest_state.hex() if tran.latest_state is not None else "Not set"
		))
		logger.info(" -> Content: %s" % TransientView.content_summary(tran))
