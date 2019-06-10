#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File              : ampel/contrib/hu/t3/TransientWebPublisher.py
# License           : BSD-3-Clause
# Author            : Jakob van Santen <jakob.van.santen@desy.de>
# Date              : 15.08.2018
# Last Modified Date: 15.08.2018
# Last Modified By  : Jakob van Santen <jakob.van.santen@desy.de>

import asyncio
import json
import time
import os
import datetime
from aiohttp import ClientSession, ClientTimeout
from aiohttp.client_exceptions import ServerDisconnectedError, ClientConnectorError
from asyncio import TimeoutError
from aiohttp.helpers import strip_auth_from_url, URL

from ampel.base.TransientView import TransientView
from ampel.base.abstract.AbsT3Unit import AbsT3Unit
from ampel.pipeline.common.ZTFUtils import ZTFUtils
from ampel.archive import ArchiveDB
from ampel.utils.json import AmpelEncoder, object_hook



class TransientWithPhotToCloud(AbsT3Unit):
    """
    Based on TransientWebPublisher
    """

    version = 0.1
    resources = ('desycloud.default', 'archive.reader')

    def __init__(self, logger, base_config=None, run_config=None, global_info=None):
        """
        """
        self.base_config = base_config
        self.run_config  = run_config
        self.global_info = global_info

        self.logger = logger
        self.count = 0
        self.dt = 0

        self.current_month = datetime.date.strftime(datetime.date.today,"%Y%m")

        # don't bother preserving immutable types
        self.encoder = AmpelEncoder(lossy=True)

        # strip username and password from URL
        url, auth = strip_auth_from_url(URL(base_config['desycloud.default'] + '/AMPEL/'))
        self.base_dest = str(url)
        self.auth = auth
        self.existing_paths = set()
        self.archive = ArchiveDB(base_config['archive.reader'])

    async def create_directory(self, session, path_parts, timeout=1.0):
        path = []
        while len(path_parts) > 0:
            path.append(path_parts.pop(0))
            if tuple(path) in self.existing_paths:
                continue

            url = os.path.join(self.base_dest, *path)
            resp = await session.request('HEAD', url)
            OK = (200, 201)
            if not resp.status in OK:
                for i in range(16):
                    resp = await session.request('MKCOL', url)
                    # in nextClould, rapid-fire MKCOL is unreliable
                    if resp.status in OK:
                        break
                    elif resp is None or resp.status in (403, 405):
                        await asyncio.sleep(timeout)
                        timeout *= 1.5
                    else:
                        resp.raise_for_status()
                if not resp.status in OK:
                    self.logger.critical(
                        "MKCOL {} failed with status {} after {} attempts".format(url, resp.status, i + 1))
                resp.raise_for_status()
            self.existing_paths.add(tuple(path))

    async def put(self, session, url, data, timeout=1.0):
        OK = (200, 201, 204)
        for i in range(16):
            try:
                resp = await session.put(url, data=data)
                if resp.status in OK:
                    break
                elif resp.status not in (403, 405, 423):
                    resp.raise_for_status()
            except (ServerDisconnectedError, ClientConnectorError, TimeoutError) as e:
                self.logger.error(e)
                pass
            finally:
                await asyncio.sleep(timeout)
                timeout *= 1.5
        if not resp.status in OK:
            self.logger.critical("PUT {} failed with status {} after {} attempts".format(url, resp.status, i + 1))
        resp.raise_for_status()

    def transient_summary(self, tran_view):
        fields = ["tran_id", "flags", "journal", "latest_state"]
        return self.encoder.encode({k: getattr(tran_view, k) for k in fields})

    def transient_is_interesting(self,tran_view):
        is_interesting = False
        for t2record in tran_view.t2records:
            if t2record['t2_unit_id'] == self.run_config['t2_unit_photometry']:
                results = t2record['results'][0]
                for lc_dict in results:
                    if 'is_brighter' in results[lc_dict]:
                        if results[lc_dict]['is_brighter'] == True:
                            is_interesting = True
                            break
                        if results[lc_dict]['trend_brighter'] == True:
                            is_interesting = True
                            break
                    if 'is_bluer' in results[lc_dict]:
                        if results[lc_dict]['is_bluer'] == True:
                            is_interesting = True
                            break
                break
        return(is_interesting)
        
    async def publish_transient(self, session, tran_view):
        ztf_name = str(ZTFUtils.to_ztf_id(tran_view.tran_id))
        channel = tran_view.channel
        assert isinstance(channel, str), "Only single-channel transients are supported"

        await self.create_directory(session, ['ZTF', channel, self.current_month, ztf_name])
        base_dir = os.path.join(self.base_dest, 'ZTF', channel, self.current_month, ztf_name)

        tasks = [
            self.put(session, base_dir + "/transient.json", data=self.transient_summary(tran_view)),
            self.put(session, base_dir + "/dump.json", data=self.encoder.encode(tran_view)),
        ]

        await asyncio.gather(*tasks)

        self.logger.info(ztf_name)

    async def publish_transient_batch(self, transients):
        async with ClientSession(auth=self.auth) as session:
            tasks = [self.publish_transient(session, tran_view) \
                for tran_view in transients \
                if self.transient_is_interesting(tran_view)]

            await asyncio.gather(*tasks)

    def add(self, transients):
        """
        """
        if transients is not None:
            batch_count = len(transients)
            self.count += batch_count

            loop = asyncio.get_event_loop()
            t0 = time.time()
            loop.run_until_complete(self.publish_transient_batch(transients))
            self.dt += time.time() - t0

    def done(self):
        """
        """
        self.logger.info("Published {} transients in {:.1f} s".format(self.count, self.dt))
