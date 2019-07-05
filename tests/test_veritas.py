#!/bin/env python


from ampel.ztf.pipeline.t0.DevAlertProcessor import DevAlertProcessor
from ampel.ztf.utils.ZIAlertUtils import ZIAlertUtils
import ampel.contrib.veritas.t0.VeritasBlazarFilter as VeritasModule
from ampel.contrib.veritas.t0.VeritasBlazarFilter import VeritasBlazarFilter
from ampel.contrib.veritas.t2.T2BlazarProducts import T2BlazarProducts
from ampel.contrib.veritas.t2.T2CatalogMatch import T2CatalogMatch

import unittest
import os
import json
import pymongo
import logging

basedir=os.path.dirname(os.path.realpath(__file__)).replace("tests","")
alertfilepath="{0}/tests/ztf_public_20190624".format(basedir)
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
        command = "mongod --dbpath /tmp/mongotest --shutdown"
        command_list = command.split()
        p = subprocess.Popen(command_list)
        p.wait()
        command = "pkill mongod"
        command_list = command.split()
        p = subprocess.Popen(command_list)
        p.wait()
        time.sleep(1)
        print("Running fresh mongod")
        os.makedirs("/tmp/mongotest",exist_ok=True)
        command = "mongod --quiet --fork --dbpath /tmp/mongotest --logpath /dev/null"
        command_list = command.split()
        p = subprocess.Popen(command_list)
        p.wait()
        time.sleep(2)

    # Restoring the databases
    print("Restoring databases from mongo dumps")
    os.makedirs("dump_veritas_blazars",exist_ok=True)
    command = "tar xvf {0}/dump_veritas_blazars.tar.gz -C dump_veritas_blazars".format(basedir)
    p = subprocess.Popen(command.split()); p.wait()
    command = "mongorestore dump_veritas_blazars"
    p = subprocess.Popen(command.split()); p.wait()
    command = "rm -rf dump_veritas_blazars"
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
        n_processed,accepted,rejected = run_T0(alertfilepath + "_accepted")
        print("%d alerts accepted by the filter (%.2f precent)" % (len(accepted), 100. * len(accepted) / n_processed))
        self.assertEqual(100. * len(accepted) / n_processed, 100)

    def test_rejected(self):
        logging.info("Testing a sample of bad alerts (should be rejected):")
        n_processed,accepted,rejected = run_T0(alertfilepath + "_rejected")
        print("%d alerts accepted by the filter (%.2f precent)" % (len(accepted), 100. * len(accepted) / n_processed))
        self.assertEqual(100. * len(accepted) / n_processed, 0)
'''


class TestT2(unittest.TestCase):
    def test_T2(self):
        logging.info("Testing a sample of good alerts (T0+T2-photometry)")
        n_processed,accepted,rejected = run_T0(alertfilepath + "_accepted")
        test_T2_photometry = T2BlazarProducts()
        test_T2_catalog    = T2CatalogMatch()

        with open('{0}/ampel/contrib/veritas/t2_run_configs.json'.format(basedir), 'r') as infile:
            data = json.load(infile)
            run_config_phot = data['T2BLAZARPRODUTCS_dynamic']['parameters']
            run_config_cat  = data['CATALOGMATCH_vheblazars']['parameters']

        for alert in accepted:
            light_curve = ZIAlertUtils._create_lc(alert.pps, alert.uls)
            out = test_T2_photometry.run(light_curve, run_config_phot)
            print('----> Excitement score: {0}'.format(out['excitement']))

            # Test write and read
            with open("output_T2blazarproduct.json", "w", newline='\n') as json_file:
                json.dump(out,json_file)
                json_file.write("\r\n")

            with open("output_T2blazarproduct.json", "r", newline='\n') as json_file:
                print(json.load(json_file))

            out = test_T2_catalog.run(light_curve, run_config_cat)

            # Test write and read
            with open("output_T2catalogmatch.json", "w", newline='\n') as json_file:
                json.dump(out,json_file)
                json_file.write("\r\n")

            with open("output_T2catalogmatch.json", "r", newline='\n') as json_file:
                print(json.load(json_file))

if __name__ == '__main__':
    unittest.main()
