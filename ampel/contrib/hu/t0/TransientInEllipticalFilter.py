#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File              : src/ampel/contrib/ztfbh/t0/LensedTransientFilter.py
# Author            : m. giomi <matteo.giomi@desy.de>
# Date              : 04.27.2018
# Last Modified Date: 06.06.2018
# Last Modified By  : danny goldstein

import logging
from extcats import CatalogQuery
from pymongo import MongoClient
from ampel.base.abstract.AbsAlertFilter import AbsAlertFilter

class TransientInEllipticalFilter(AbsAlertFilter):

    """Filter to select gravitationally lensed transients by cross
    matching them against an elliptical galaxy catalog and comparing
    their brightness to that of a type Ia supernova at the redshift
    of the elliptical.
    
    The method is described in detail in Goldstein & Nugent (2017):
    http://adsabs.harvard.edu/abs/2017ApJ...834L...5G
    """

    # Static version info
    version = 1.0
    resources = ('extcats.reader',)

    def __init__(self, on_match_t2_units, base_config=None, run_config=None, logger=None):

        if run_config is None or len(run_config) == 0:
            raise ValueError("Please check your run configuration")
        
        self.on_match_t2_units = on_match_t2_units
        self.logger = logger if logger is not None else logging.getLogger()
        
        # filter parameters
        self.search_radius = run_config['search_radius']
        self.absmag_thresh = run_config['absmag_thresh']
        self.rb_th = run_config['rb_th']
        
        # init the catalog query object for the star catalog
        catq_client = MongoClient(base_config['extcats.reader'])
        self.sdss_query = CatalogQuery.CatalogQuery(
                                                    "redlenses",
                                                    ra_key='ra', dec_key='dec',
                                                    logger=logger, dbclient=catq_client
                                                    )
            
        self.logger.info(
            "Search radius for ellipticals: %.2f arcsec" % self.search_radius)

    def apply(self, alert):

        # select latest pp
        latest = alert.pps[0]
        
        # cut on real-bogus
        rb = latest['rb']
        if rb < self.rb_th:
            self.logger.debug("rejected: RB score %.2f below threshold (%.2f)" % (rb, self.rb_th))
            return None
        
        # cut on positive subtraction (sci image brighter than reference)
        if not (
                latest['isdiffpos'] and 
                (latest['isdiffpos'] == 't' or latest['isdiffpos'] == '1')
            ):
            self.logger.debug("rejected: 'isdiffpos' is %s", latest['isdiffpos'])
            return None

        # check for matching in lens catalog
        ra, dec = latest['ra'], latest['dec']
        entry, dist = self.sdss_query.findclosest(ra, dec, self.search_radius)
        if entry is None:
            self.logger.debug("rejected: not within %.2e arcsec of a known SDSS elliptical" % self.search_radius)
            return None

        self.logger.debug('lensed SN candidate')
        return self.on_match_t2_units
