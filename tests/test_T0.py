import unittest

class TestT0(unittest.TestCase):
    def test_accepted(self):
        dap = DevAlertProcessor(my_filter, use_dev_alerts=True)
        n_processed = dap.process_tar(alertfilepath + "_accepted", tar_mode='r', iter_max=2000)

        accepted = dap.get_accepted_alerts()
        rejected = dap.get_rejected_alerts()
        print("%d alerts accepted by the filter (%.2f precent)" % (len(accepted), 100. * len(accepted) / n_processed))
        print("%d alerts rejected by the filter (%.2f precent)" % (len(rejected), 100. * len(rejected) / n_processed))
        self.assertEqual(100. * len(accepted) / n_processed, 100)
        self.assertEqual(  0. * len(rejected) / n_processed, 100)
    def test_rejected(self):
        dap = DevAlertProcessor(my_filter, use_dev_alerts=True)
        n_processed = dap.process_tar(alertfilepath + "_rejected", tar_mode='r', iter_max=2000)

        accepted = dap.get_accepted_alerts()
        rejected = dap.get_rejected_alerts()
        print("%d alerts accepted by the filter (%.2f precent)" % (len(accepted), 100. * len(accepted) / n_processed))
        print("%d alerts rejected by the filter (%.2f precent)" % (len(rejected), 100. * len(rejected) / n_processed))
        self.assertEqual(  0. * len(accepted) / n_processed, 100)
        self.assertEqual(100. * len(rejected) / n_processed, 100)

if __name__ == '__main__':
    unittest.main()
