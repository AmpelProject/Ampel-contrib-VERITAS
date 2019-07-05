#!/bin/env python


from ampel.ztf.pipeline.t0.DevAlertProcessor import DevAlertProcessor
import ampel.contrib.veritas.t0.VeritasBlazarFilter as VeritasModule
from ampel.contrib.veritas.t0.VeritasBlazarFilter import VeritasBlazarFilter

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
        command = "mongod --quiet --fork --dbpath /tmp/mongotest --logpath /tmp/mongo.log"
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

def make_diagnostic_plots(list_of_alerts,output_file=None):
    import numpy as np
    import matplotlib as mpl
    mpl.rcParams['figure.dpi'] = 120
    mpl.rcParams['savefig.dpi'] = 120
    import matplotlib.pyplot as plt

    variables = ["magpsf", "sharpnr", "ndethist",
                 "distpsnr1", "scorr", "sgscore1",
                 "rb", "ssnrms"]

    fig = plt.figure()
    for k in range(len(variables)):
        ax = fig.add_subplot(3, 3, k + 1)
        values = [alert.get_values(variables[k])[0] for alert in list_of_alerts]

        lims = max(min(values), np.percentile(values, 1) * 0.5), \
               min(max(values), np.percentile(values, 80) * 2)
        ax.set_xlim(lims)
        ax.hist(values, bins=(np.linspace(lims[0], lims[-1], 50)))
        # ax.set_ylabel("Frequency")
        ax.set_xlabel(variables[k])
    plt.tight_layout()
    if output_file is not None:
        plt.savefig(output_file)
    else:
        plt.show()
    return(fig)


class TestT0(unittest.TestCase):
    def test_accepted(self):
        logging.info("Testing a sample of good alerts (should be accepted):")
        dap = DevAlertProcessor(my_filter, use_dev_alerts=False)
        n_processed = dap.process_tar(alertfilepath + "_accepted", tar_mode='r', iter_max=2000)
        accepted = dap.get_accepted_alerts()
        rejected = dap.get_rejected_alerts()
        print("%d alerts accepted by the filter (%.2f precent)" % (len(accepted), 100. * len(accepted) / n_processed))
        self.assertEqual(100. * len(accepted) / n_processed, 100)

    def test_rejected(self):
        logging.info("Testing a sample of bad alerts (should be rejected):")
        dap = DevAlertProcessor(my_filter, use_dev_alerts=False)
        n_processed = dap.process_tar(alertfilepath + "_rejected", tar_mode='r', iter_max=2000)
        accepted = dap.get_accepted_alerts()
        print("%d alerts accepted by the filter (%.2f precent)" % (len(accepted), 100. * len(accepted) / n_processed))
        self.assertEqual(100. * len(accepted) / n_processed, 0)

if __name__ == '__main__':

    run_mongo_if_needed()
    with open('{0}/ampel/contrib/veritas/channels.json'.format(basedir), 'r') as infile:
        data = json.load(infile)
        run_config = HackDict(data[0]['sources']['t0Filter']['runConfig'])

    base_config = {
        'extcats.reader': None
    }

    my_filter = VeritasBlazarFilter( \
        on_match_t2_units=['T2BlazarProducts'],
        run_config=run_config,
        base_config=base_config)

    unittest.main()