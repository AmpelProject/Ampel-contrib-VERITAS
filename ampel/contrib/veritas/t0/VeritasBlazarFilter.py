#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File              : ampel/contrib/veritas/t0/VeritasBlazarFilter.py
# License           : BSD-3-Clause
# Author            : m. nievas-rosillo <mireia.nievas-rosillo@desy.de>
# Date              : 06.09.2018
# Last Modified Date: 06.09.2018
# Last Modified By  : m. nievas-rosillo <mireia.nievas-rosillo@desy.de>

import sys
import numpy as np
import logging
from pymongo import MongoClient
from urllib.parse import urlparse
from extcats import CatalogQuery
from astropy.coordinates import SkyCoord
from astropy.table import Table
from pydantic import BaseModel

from ampel.base.abstract.AbsAlertFilter import AbsAlertFilter


class VeritasBlazarFilter(AbsAlertFilter):
    """
    VERITAS blazar filter
    """

    # Static version info
    version = 1.0
    resources = ('extcats.reader',)

    class RunConfig(BaseModel):
        """
        Necessary class to validate the configuration
        """
        RECOMMENDED_CUTS: int   = 0       # recommended cuts for a clean sample (should not be needed)
        MIN_NDET        : int   = 2       # number of previous detections
        MIN_RB          : float = 0.50    # real bogus score
        MIN_MAG         : float = 9.0     # brightness threshold [mag]
        MAX_MAG         : float = 20.0    # brightness threshold [mag]
        MAX_BAD         : int   = 0       # Maximum number of bad pixels in a 5x5 stamp.
        MAX_ELONG       : float = 1.3     # aimage/bimage (major/minor axes)
        MAX_FWHM        : float = 5.0     # maximum FWHM
        MAX_MAGDIFF     : float = 1.3     # diff ap - psf phot
        SCORR           : float = 0.0     # peak pixel signal-to-noise ratio
        SSNRMS          : float = 0.0     # S/stddev(S) where S=conv(D,PSF)
        MIN_SHARPNESS   : float = -2      # star-like ~ 0, CRs < 0, extended > 0
        MAX_SHARPNESS   : float = +2      # star-like ~ 0, CRs < 0, extended > 0
        DIST_PSNR1      : float = 0.5     # distance to closest src of PS1 catalog.
        SGS_SCORE1      : float = 0.9     # how likely it is that src to be a star.
        CATALOGS_ARCSEC : dict  = {
            "VERITAS_BLAZARS:GammaCAT": 40,
            "VERITAS_BLAZARS:4LAC": 20,
            "VERITAS_BLAZARS:4LAC_lowlat": 20,
            "VERITAS_BLAZARS:3FHL": 20,
            "VERITAS_BLAZARS:4FGL": 20,
            "VERITAS_BLAZARS:2WHSP": 2,
            "VERITAS_BLAZARS:RomaBZCAT": 2,
            "VERITAS_BLAZARS:XRaySelBLL": 2,
            "VERITAS_BLAZARS:Plotkin10": 2,
            "VERITAS_BLAZARS:BeppoSAXblazars": 5,
            "VERITAS_BLAZARS:FRICAT": 10,
            "VERITAS_BLAZARS:FRIICAT": 10,
            "VERITAS_BLAZARS:MILLIQUAS": 1
        }

    def __init__(self, on_match_t2_units, base_config=None, run_config=None, logger=None):
        """
        """
        if run_config is None or len(run_config.dict()) == 0:
            raise ValueError("Please check you run configuration")
        
        self.keys_to_check = ('ndet', 'ra', 'dec', 'rb', 'scorr', 'ssnrms', 
                              'magpsf', 'distpsnr1', 'sgscore1', 'ndethist')

        self.on_match_t2_units = on_match_t2_units
        self.logger = logger if logger is not None else logging.getLogger()
        self.rejected_reason = {}

        # parse the run config
        rc_dict = run_config.dict()
        for k, val in rc_dict.items():
            self.logger.info("Using %s=%s" % (k, val))
        
        # ----- set filter properties ----- #
        self.recommended_cuts                  = rc_dict['RECOMMENDED_CUTS']
        self.min_ndet                          = rc_dict['MIN_NDET']
        self.rb_th                             = rc_dict['MIN_RB']
        self.min_mag                           = rc_dict['MIN_MAG']
        self.max_mag                           = rc_dict['MAX_MAG']
        self.max_bad                           = rc_dict['MAX_BAD']
        self.max_elong                         = rc_dict['MAX_ELONG']
        self.max_fwhm                          = rc_dict['MAX_FWHM']
        self.max_magdiff                       = rc_dict['MAX_MAGDIFF']
        self.scorr                             = rc_dict['SCORR']
        self.ssnrms                            = rc_dict['SSNRMS'] 
        self.min_sharpness                     = rc_dict['MIN_SHARPNESS']
        self.max_sharpness                     = rc_dict['MAX_SHARPNESS']
        self.max_distpsnr1                     = rc_dict['DIST_PSNR1']
        self.max_sgscore1                      = rc_dict['SGS_SCORE1']
        self.catalogs_arcsec                   = rc_dict['CATALOGS_ARCSEC']

        # ----- init the catalog query object for the 3fhl catalog ----- #
        catq_client = MongoClient(base_config['extcats.reader'])
        catq_kwargs = {'logger': self.logger, 'dbclient': catq_client}
        self.db_queries = {}
        #for catq in catq_client.list_database_names():
        #    # loop over databases
        #    if catq in ['admin','local','config']: continue
        
        for catq in self.catalogs_arcsec:
            if catq not in catq_client.list_database_names():
                self.logger.error("Catalog {0} not in the Mongo DB".format(catq))

            self.db_queries[catq] = \
                CatalogQuery.CatalogQuery(catq, ra_key='RAJ2000', dec_key='DEJ2000',
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
        
        if self.recommended_cuts == 1:
            # Apart from the specified cuts we can do the recommended cuts from tests done at IPAC
            # From https://github.com/ZwickyTransientFacility/ztf-avro-alert/blob/master/docs/filtering.md
            if (latest['rb']    < 0.65):  return None
            if (latest['nbad']  > 0):     return None
            if (latest['fwhm']  > 5):     return None
            if (latest['elong'] > 1.2):   return None
            if np.abs(latest['magdiff'] > 0.1): return None
        
        if latest['nbad'] > self.max_bad:
            self.logger.debug("rejected: NBAD %d above threshold (%d)" %
                (latest['nbad'], self.max_bad))
            self.reason='high_nbad'
            self.rejected_reason[latest['candid']] = self.reason
            return None
        
        if latest['rb'] < self.rb_th:
            self.logger.debug("rejected: RB score %.2f below threshold (%.2f)" %
                (latest['rb'], self.rb_th))
            self.reason='low_rb'
            self.rejected_reason[latest['candid']] = self.reason
            return None
        
        if latest['elong'] > self.max_elong:
            self.logger.debug("rejected: ELONG score %.2f above threshold (%.2f)" %
                (latest['elong'], self.max_elong))
            self.reason='high_elong'
            self.rejected_reason[latest['candid']] = self.reason
            return None
        
        if latest['fwhm'] > self.max_fwhm:
            self.logger.debug("rejected: FWHM score %.2f above threshold (%.2f)" %
                (latest['fwhm'], self.max_fwhm))
            self.reason='high_fwhm'
            self.rejected_reason[latest['candid']] = self.reason
            return None
        
        if np.abs(latest['magdiff']) > self.max_magdiff:
            self.logger.debug("rejected: MAGDIFF %.2f above threshold (%.2f)" %
                (latest['magdiff'], self.max_magdiff))
            self.reason='high_magdiff'
            self.rejected_reason[latest['candid']] = self.reason
            return None
        
        if latest['scorr'] < self.scorr:
            self.logger.debug("rejected: SCORR (SNR) %.2f < %.2f" %
                (latest['scorr'], self.scorr))
            self.reason='low_scorr'
            self.rejected_reason[latest['candid']] = self.reason
            return None
        
        if latest['ssnrms'] < self.ssnrms:
            self.logger.debug("rejected: SSNRMS (SNR) %.2f < %.2f" %
                (latest['ssnrms'], self.ssnrms))
            self.reason='low_ssnrms'
            self.rejected_reason[latest['candid']] = self.reason
            return None

        # cut on magnitude (bandpass, min<mag<max)
        if (latest['magpsf'] < self.min_mag):
            self.logger.debug("rejected: magpsf %.2f < %.2f" %
                (latest['magpsf'], self.min_mag))
            self.reason='low_mag'
            self.rejected_reason[latest['candid']] = self.reason
            return None
        elif (latest['magpsf'] > self.max_mag):
            self.logger.debug("rejected: magpsf %.2f > %.2f" %
                (latest['magpsf'], self.max_mag))
            self.reason='high_mag'
            self.rejected_reason[latest['candid']] = self.reason
            return None
        
        # check sharpness (to remove cosmic rays, negative values)
        # http://stsdas.stsci.edu/cgi-bin/gethelp.cgi?peak
        if (latest['sharpnr']) < self.min_sharpness:
            # likely a cosmic ray
            self.reason='cosmic_ray_sharpness'
            self.rejected_reason[latest['candid']] = self.reason
            return None
        elif (latest['sharpnr']) > self.max_sharpness:
            # likely an extended source
            self.reason='extended_src_sharpness'
            self.rejected_reason[latest['candid']] = self.reason
            return None
            
        # check for positional coincidence with known star-like objects.
        if (latest['distpsnr1']) < self.max_distpsnr1:
            if (latest['sgscore1']) > self.max_sgscore1:
                # likely a star
                self.reason='ps1_cat_star'
                self.rejected_reason[latest['candid']] = self.reason
                return None
            
        # since it was detected only once, it might be an object with 
        # a large proper motion (i.e. solar system or closeby star)
        if latest['ndethist'] < self.min_ndet:
            self.logger.debug("rejected: only detected once")
            self.reason='one_time_detection'
            self.rejected_reason[latest['candid']] = self.reason
            return None
        
        # check if it is at least as bright in one of the bands
        
        alert_filters = np.asarray(alert.get_values('fid'))
        alert_magpsfs = np.asarray(alert.get_values('magpsf'))
        keep_alert = False
        for filt in np.unique(alert_filters):
            average = np.median(alert_magpsfs[alert_filters==filt])
            if alert_magpsfs[0] <= average:
                keep_alert = True
        if not keep_alert:
            self.logger.debug("rejected: not enough photo points")
            self.reason='not_brighter'
            self.rejected_reason[latest['candid']]=self.reason
            return None
        
        # check for positional coincidence with gamma-ray blazars
        for catq in self.db_queries:
            currentcat = self.db_queries[catq]
            rs_arcsec  = self.catalogs_arcsec[catq]
            matchfound = currentcat.binaryserach(\
                latest['ra'], latest['dec'], rs_arcsec)
            if matchfound:
                return self.on_match_t2_units
         
        self.logger.debug("rejected: not in catalogs")
        
        self.reason='not_in_catalogs'
        self.rejected_reason[latest['candid']] = self.reason    
        
        return None
                
