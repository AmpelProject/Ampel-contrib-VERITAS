#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File          : ampel/contrib/hu/t3/MarshalPublisher.py
# License       : BSD-3-Clause
# Author        : jn <jnordin@physik.hu-berlin.de>
# Date          : 19.06.2018
# Last Modified Date: 19.06.2018
# Last Modified By  : jn <jnordin@physik.hu-berlin.de>
#
# Notes about the (Growth) Marshal. There are similarities with AMPEL, but also significant differences.
#
# Overview: The Marshal contains a set of stored *transients*. A user belongs to a set of science *programs*. A transients which has been *saved* by any of the science programs
# that a user is a member of can be *seen* by that user. A users has access to all information belong ot a transient, irrespectively of who added it.
#
# Each program can define a basic filter which filters the incoming alert flow. All transients that pass a filter are *ingested* to the scan candidate page, in which a user
# selects which program to scan for. Displayed transients can then be *saved* into that science program through a button.
#
# Transients saved into the marshal contain the basic lightcurve. There are also facilities to display spectra. Further, there are *auto-annotations* which are meant to be added
# pieces of information. Can typically be redshift of an associated host galaxy. There are allso *comments*, which are free text entered by a user into the marshal page. These
# can have certain types of prefixes added (e.g. type).
#
# Why am I writing this? Because this class eventually has to find ways to interact, meaning exchanging information in both directions,
# with all *stared* items in a reasonably way. The sergeant communicates with the marshal either through directly parsing the web page or through cgi-scripts. Both
# methods can be very slow, especially the first.
#
# v.01 of this method only contains the very first bit of information: Ingesting an alert into the marshal based on avro id.
#
# Todo:
# Keep track of what was ingested

from ampel.base.abstract.AbsT3Unit import AbsT3Unit
from ampel.pipeline.t3.sergeant import marshal_functions
from ampel.pipeline.logging.LoggingUtils import LoggingUtils

class MarshalPublisher(AbsT3Unit):
    """
    """

    version = 0.1

    def __init__(self, logger, base_config=None, run_config=None, global_info=None):
        """
        """
        self.logger = LoggingUtils.get_logger() if logger is None else logger
        self.base_config = base_config
        self.run_config = run_config
        self.toingest = []
        self.ingested = []
        self.failingest = []


    def add(self, transients):
        """
        """
        self.toingest += transients 


    def done(self):
        """
        """

        self.logger.info("Running with run config %s" % self.run_config)

        # Instansiate the Marshal Sergeant.
        # For now we ignore the option of giving date ranges
        ser = marshal_functions.Sergeant(
            self.run_config['marshal_program'], 
            marshalusr=self.run_config['marshal_userID'], 
            marshalpwd=self.run_config['marshal_userpwd']
        )

        if self.run_config['ingest_all']:
        
            # Loop through provided transients
            for tview in self.toingest:

                # Ingest the latest photopoint (not sure they are available at a later time!)
                alertid, maxJD = None, 0

                for x in tview.photopoints:
                    if x.get_value("jd") > maxJD:
                        alertid = x.get_id()
                        maxJD = x.get_value('jd')

                if maxJD > 0:

                    report = ser.ingest_avro_id(str(alertid))

                    if report == 200:
                        self.ingested.append(alertid)
                    else:
                        self.failingest.append(alertid)

                else:
                    self.failingest.append(tview.tran_id)

            self.toingest = []


        self.logger.info(
            "Ingesting transients to marshal program %s. HTTP success %s, fail %s" %
            (self.run_config['marshal_program'], self.ingested, self.failingest)
        )

