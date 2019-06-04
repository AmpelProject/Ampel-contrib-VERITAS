#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File              : ampel/contrib/hu/t3/SlackSummaryPublisher.py
# License           : BSD-3-Clause
# Author            : mireia nievas
# Date              : 04.06.2019
# Last Modified Date: 04.06.2019
# Last Modified By  : MNR <mireia.nievas-rosillo@desy.de>

import pandas as pd
import numpy as np
import collections
import io, pickle, datetime, requests
from slackclient import SlackClient
from slackclient.exceptions import SlackClientError
from pydantic import BaseModel
from typing import Dict, List, Union
from ampel.base.abstract.AbsT3Unit import AbsT3Unit
from ampel.ztf.pipeline.common.ZTFUtils import ZTFUtils
from ampel.pipeline.common.AmpelUtils import AmpelUtils
from ampel.pipeline.logging.AmpelLogger import AmpelLogger
from ampel.pipeline.config.EncryptedConfig import EncryptedConfig

class SlackPublishTrigger(AbsT3Unit):
	class RunConfig(BaseModel):
		quiet: bool = False
		slackChannel: str 
        slackToken: Union[str, EncryptedConfig]
		excitement: Dict[str, int] = {"Low": 50,"Mid": 200,"High": 400}
		fullPhotometry: bool = False
		cols: List[str] = [
            "ztf_name","ra","dec","magpsf","sgscore1","rb", 
			"last_significant_nondet", "first_detection",
            "most_recent_detection","n_detections",
            "distnr","distpsnr1","isdiffpos","_id"
            ]
	
	def __init__(self, logger, base_config=None, run_config=None, global_info=None):
        """
        """
        self.logger = AmpelLogger.get_logger() if logger is None else logger
        self.run_config = run_config
        self.frames = []
        self.photometry = []
        self.channels = set()

	def publish_alert(

	def done(self):
		if len(self.frames) == 0 and self.run_config.quiet:
            return
   
        date = str(datetime.date.today())

        sc = SlackClient(self.run_config.slackToken)

        m = calculate_excitement(len(self.frames), date=date,
            thresholds=self.run_config.excitement
        )

		

