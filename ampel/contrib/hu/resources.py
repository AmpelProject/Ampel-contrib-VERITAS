#!/usr/bin/env python
# -*- coding: utf-8 -*-
# License           : BSD-3-Clause
# Author            : Jakob van Santen <jakob.van.santen@desy.de>
from ampel.pipeline.config.resources import ResourceURI
from urllib.parse import urlparse

class extcatsURI(ResourceURI):
    
    name = "extcats"
    fields = ('hostname', 'port')
    roles = ('reader', 'writer')
    
    @classmethod
    def get_default(cls):
        return dict(scheme='mongodb', hostname='localhost', port=27017)
    
    def __call__(self):
        return self.uri

class catsHTMPath(ResourceURI):
    
    name = "catsHTM"
    fields = ('path',)
    
    @classmethod
    def get_default(cls):
        return dict(scheme='file')
    
    def __call__(self):
        return urlparse(self.uri).path

class desyCloudURI(ResourceURI):

    name = "desycloud"
    fields = ('username', 'password')

    @classmethod
    def get_default(cls):
        return dict(scheme='https', hostname='desycloud.desy.de', path='remote.php/webdav')

    def __call__(self):
        return self.uri
