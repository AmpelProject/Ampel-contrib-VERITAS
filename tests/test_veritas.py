#!/bin/env python


from ampel.ztf.pipeline.t0.DevAlertProcessor import DevAlertProcessor
from ampel.ztf.utils.ZIAlertUtils import ZIAlertUtils
import ampel.contrib.veritas.t0.VeritasBlazarFilter as VeritasModule
from ampel.contrib.veritas.t0.VeritasBlazarFilter import VeritasBlazarFilter
from ampel.contrib.veritas.t2.T2BlazarProducts import T2BlazarProducts
from ampel.contrib.veritas.t2.T2CatalogMatch import T2CatalogMatch

import pytest
import unittest
import os
import json
import pymongo
import logging
import shutil

basedir=os.path.dirname(os.path.realpath(__file__)).replace("tests","")
alertfilepath="{0}/tests/ztf_test".format(basedir)
mongodbpath = "/tmp/mongodb"


def run_mongo_if_needed():
    import subprocess
    import time
    import os
    try:
        print("Testing MongoDB connection")
        c = pymongo.MongoClient(connectTimeoutMS=2000,
                                serverSelectionTimeoutMS=2000,
                                waitQueueTimeoutMS=2000,
                                socketTimeoutMS=2000)
        c.server_info()
    except:
        print("MongoDB not running")

    #command = "pkill mongod"
    #shutil.rmtree('/tmp/mongotest', ignore_errors=True)
    command = "mongod --dbpath /tmp/mongotest --shutdown"
    command_list = command.split()
    p = subprocess.Popen(command_list)
    p.wait()
    command = "pkill mongod"
    command_list = command.split()
    p = subprocess.Popen(command_list)
    p.wait()
    time.sleep(1)
    command = "rm -rf /tmp/mongotest"
    command_list = command.split()
    p = subprocess.Popen(command_list)
    p.wait()
    print("Running fresh mongod")
    os.makedirs("/tmp/mongotest",exist_ok=True)
    command = "mongod --quiet --fork --dbpath /tmp/mongotest --logpath /dev/null"
    command_list = command.split()
    p = subprocess.Popen(command_list)
    p.wait()
    time.sleep(2)

    # Restoring the databases
    print("Restoring databases from mongo dumps")
    #os.makedirs("dumps_veritas_blazars",exist_ok=True)
    command = "tar xvf {0}/dumps_veritas_blazars.tar.gz -C ./".format(basedir)
    p = subprocess.Popen(command.split()); p.wait()
    command = "mongorestore --quiet dumps_veritas_blazars"
    p = subprocess.Popen(command.split()); p.wait()
    command = "rm -rf dumps_veritas_blazars"
    p = subprocess.Popen(command.split()); p.wait()

class HackDict(dict):
    '''
    emulates conversion to dict
    '''
    def __init__(self,item):
        self.item = item
    def dict(self):
        return(self.item)

def run_T0(alert_file,iter_max=2000):
    run_mongo_if_needed()

    with open('{0}/ampel/contrib/veritas/channels.json'.format(basedir), 'r') as infile:
        data = json.load(infile)
        run_config = HackDict(data[0]['sources']['t0Filter']['runConfig'])

    base_config = {
        'extcats.reader': None
    }

    test_T0 = VeritasBlazarFilter( \
        on_match_t2_units=['T2BlazarProducts'],
        run_config=run_config,
        base_config=base_config)

    dap = DevAlertProcessor(test_T0, use_dev_alerts=False)
    n_processed = dap.process_tar(alert_file, tar_mode='r', iter_max=iter_max)
    accepted = dap.get_accepted_alerts()
    rejected = dap.get_rejected_alerts()
    return(n_processed,accepted,rejected)

'''
class TestT0(unittest.TestCase):
    def test_accepted(self):
        logging.info("Testing a sample of good alerts (should be accepted):")
        n_processed,accepted,rejected = run_T0(alertfilepath + ".accepted.tar.gz")
        print("%d alerts accepted by the filter (%.2f precent)" % (len(accepted), 100. * len(accepted) / n_processed))
        #self.assertEqual(100. * len(accepted) / n_processed, 100)

    def test_rejected(self):
        logging.info("Testing a sample of bad alerts (should be rejected):")
        n_processed,accepted,rejected = run_T0(alertfilepath + ".rejected.tar.gz")
        print("%d alerts accepted by the filter (%.2f precent)" % (len(accepted), 100. * len(accepted) / n_processed))
        self.assertEqual(100. * len(accepted) / n_processed, 0)
'''
# skip this in automated testing, as it does not assert anything
@pytest.mark.skip
class TestT2(unittest.TestCase):
    def test_T2(self):
        logging.info("Testing a sample of good alerts (T0+T2-photometry)")
        n_processed,accepted,rejected = run_T0(alertfilepath + ".accepted.tar.gz")
        test_T2_photometry = T2BlazarProducts()
        test_T2_catalog    = T2CatalogMatch()
        #test_T3_webpub     = TransientWebPublisher()

        with open('{0}/ampel/contrib/veritas/t2_run_configs.json'.format(basedir), 'r') as infile:
            data = json.load(infile)
            run_config_phot = data['T2BLAZARPRODUTCS_dynamic']['parameters']
            run_config_cat  = data['CATALOGMATCH_vheblazars']['parameters']

        for alert in accepted:
            light_curve = ZIAlertUtils._create_lc(alert.pps, alert.uls)
            out_phot = test_T2_photometry.run(light_curve, run_config_phot)
            out_cat  = test_T2_catalog.run(light_curve, run_config_cat) 
            
            print('=============================================================')
            print('Alert: {0}'.format(alert.get_id()))
            print(' --> Excitement score: {0}'.format(out_phot['excitement']))
            print(' --> T2Cat: {0}'.format(out_cat))
            print('=============================================================')

            # Test write and read
            with open("output_T2blazarproduct.json", "w", newline='\n') as json_file:
                json.dump(out,json_file)
                json_file.write("\r\n")

            # Test write and read
            with open("output_T2blazarproduct.json", "w", newline='\n') as json_file:
                json.dump(out_phot,json_file)
                json_file.write("\r\n")

            with open("output_T2blazarproduct.json", "r", newline='\n') as json_file:
                pass #print(json.load(json_file))

            # Test write and read
            with open("output_T2catalogmatch.json", "w", newline='\n') as json_file:
                json.dump(out,json_file)
                json_file.write("\r\n")

            # Test write and read
            with open("output_T2catalogmatch.json", "w", newline='\n') as json_file:
                json.dump(out_cat,json_file)
                json_file.write("\r\n")

            with open("output_T2catalogmatch.json", "r", newline='\n') as json_file:
                pass #print(json.load(json_file))

@pytest.mark.remote_data
@pytest.fixture
def multiple_photopoint_lightcurve():
    from urllib.request import urlopen
    import gzip
    from ampel.utils import json_serialization
    with gzip.open(urlopen("https://github.com/mireianievas/Ampel-contrib-VERITAS/files/3467897/5d4578ae74dd99059e8c24f7.json.gz")) as f:
        return next(json_serialization.load(f))

def test_bayesian_blocks_with_multi_photopoints(multiple_photopoint_lightcurve, t2_run_config):
    """
    Test robustness against multiple photopoints from the same exposure
    
    See: https://github.com/mireianievas/Ampel-contrib-VERITAS/issues/2
    """
    from collections import defaultdict
    unit = T2BlazarProducts()
    # build a list of (possibly duplicated) photopoints
    ppo = defaultdict(list)
    for item in multiple_photopoint_lightcurve.ppo_list:
        ppo[tuple(item.get_value(k) for k in ('jd','fid'))].append(item)
    assert any(len(items)>1 for items in ppo), "light curve contains duplicated photopoints"
    keys = set()
    for item in unit.get_unique_photopoints(multiple_photopoint_lightcurve):
        key = tuple(item.get_value(k) for k in ('jd','fid'))
        assert key not in keys, "photopoints are unique"
        keys.add(key)
        assert all(dup.get_value('rb') <= item.get_value('rb') for dup in ppo[key]), "selected photopoint has highest score"
    T2BlazarProducts().run(multiple_photopoint_lightcurve, t2_run_config)

if __name__ == '__main__':
    unittest.main()
