#!/usr/bin/env python
# -*- coding: utf-8 -*-
# License           : BSD-3-Clause
# Author            : Jakob van Santen <jakob.van.santen@desy.de>
from ampel.config.resources import ResourceURI
from urllib.parse import urlparse

class extcatsURI(ResourceURI):
    
    name = "extcats"
    fields = ('hostname', 'port')
    roles = ('reader', 'writer')
    
    @classmethod
    def get_default(cls):
        return dict(scheme='mongodb', hostname='localhost', port=27017)

class catsHTMURI(ResourceURI):
    
    name = "catsHTM"
    fields = ('hostname', 'port')
    
    @classmethod
    def get_default(cls):
        return dict(scheme='tcp', hostname='localhost', port=27025)

    @classmethod
    def parse_args(cls, args):
        uris = super(catsHTMURI, cls).parse_args(args)
        # strip trailing slash to keep zeromq happy
        return {k: v[:-1] for k,v in uris.items()}

class desyCloudURI(ResourceURI):

    name = "desycloud"
    fields = ('username', 'password')

    @classmethod
    def get_default(cls):
        return dict(scheme='https', hostname='desycloud.desy.de', path='remote.php/webdav')
