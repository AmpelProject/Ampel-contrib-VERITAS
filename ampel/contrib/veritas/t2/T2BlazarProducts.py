from ampel.base.abstract.AbsT2Unit import AbsT2Unit
import logging
import numpy as np
import itertools

class T2BlazarProducts(AbsT2Unit):
    version = 1.0
    author = "mireia.nievas-rosillo@desy.de"
    private = False
    upperLimits = False

    default_config = {
        'max_order': 2,
        'calculate_color': True
    }

    def __init__(self, logger=None, base_config=None):
        """

        ! TODO: UPDATE OUTDATED DOCSTRING !
        ***********************************

        ':param logger': instance of logging.Logger (std python module 'logging')
            -> example usage: logger.info("this is a log message")
        ':param base_config': optio+nal dict loaded from ampel config section.
        """

        # Save the logger as instance variable
        super().__init__(logger)
        self.logger = logger if logger is not None else logging.getLogger()
        self.base_config = self.default_config if base_config is None else base_config
        self.data_filter = {}
        self.uls_filter = {}
        self.colordict = {1: 'g', 2: 'r', 3: 'i'}  # i is not really used
        self.results = dict()

    def classify_in_filters(self, light_curve):
        '''
        Classify the photometric points in filter groups.
        :param light_curve:  object containing the photometry points
                             (ppo_list) and upper limits (ulo_list)
        :return: None (fills the available_color, data_filter and uls_filter properties)
        '''
        for item in light_curve.ppo_list:
            # item['mjd'] = item['jd']-2400000.5
            if item.get_value('fid') not in self.data_filter:
                self.data_filter[item.get_value('fid')] = []
            self.data_filter[item.get_value('fid')].append(item.content)

        for item in light_curve.ulo_list:
            # item['mjd'] = item['jd']-2400000.5
            if item.get_value('fid') not in self.uls_filter:
                self.uls_filter[item.get_value('fid')] = []
            self.uls_filter[item.get_value('fid')].append(item.content)

        self.available_colors = sorted(list(self.data_filter.keys()))

    def iterative_polymodelfit(self, x, y):
        self.logger.info("Performing a polynomial fit of the data")
        if len(y) < 3:
            return (None, None)
        poly, res = np.polyfit(x, y, 1, full=True)[0:2]
        chisq_dof = (res / (len(x) - 2))[0]
        for k in range(self.run_config['max_order']):
            if len(y) > k + 3:
                self.logger.debug('Trying poly({0}) shape'.format(k + 2))
                poly_new, res_new = np.polyfit(x, y, k + 2, full=True)[0:2]
                if len(res_new) == 0: break
                chisq_dof_new = (res_new / (len(x) - (k + 3)))[0]
                if chisq_dof_new < chisq_dof * 0.8:
                    poly, res = poly_new, res_new
                    chisq_dof = chisq_dof_new
        return poly, chisq_dof

    def photometry_estimation(self, color):
        cthis = self.colordict[color]
        self.logger.info("Photometry of filter {0}".format(cthis))
        photresult = dict()
        cit = self.data_filter[color]
        photresult['jds_val'] = np.asarray([item['jd'] for item in cit])
        photresult['jds_err'] = np.asarray([0 for item in cit])
        photresult['mag_val'] = np.asarray([item['magpsf'] for item in cit])
        photresult['mag_err'] = np.asarray([item['sigmapsf'] for item in cit])
        # uls
        cit = [] if color not in self.uls_filter else self.uls_filter[color]
        photresult['uls_jds_val'] = np.asarray([item['jd'] for item in cit])
        photresult['uls_jds_err'] = np.asarray([0 for item in cit])
        photresult['uls_mag'] = np.asarray([item['diffmaglim'] for item in cit])

        photresult['quantity'] = 'mag'
        photresult['label'] = 'phot_mag_{0}'.format(cthis)
        # check if the source is becoming significantly brighter
        mean_mag = np.mean(photresult['mag_val'][:-1])
        mean_mag_err = np.std(photresult['mag_val'][:-1])
        last_mag = photresult['mag_val'][-1]
        last_mag_err = photresult['mag_err'][-1]
        is_brighter = last_mag + last_mag_err < mean_mag - mean_mag_err
        photresult['is_brighter'] = is_brighter
        # Fit the trend by a polynomium of degree 2,3 or 4
        coef, chi2 = self.iterative_polymodelfit(x=photresult['jds_val'], y=photresult['mag_val'])
        photresult['poly_coef'], photresult['poly_chi2'] = coef, chi2
        if photresult['poly_coef'][-1] < 0:
            photresult['trend_brighter'] = True
        else:
            photresult['trend_brighter'] = False
        # append everything
        self.results[photresult['label']] = photresult
        return photresult

    def is_valid_pair_for_color(self, item1, item2, max_jdtimediff=1):
        if item1['fid'] == item2['fid']:
            self.logger.debug("Data was taken with the same filter")
            return False
        if abs(item1['jd'] - item2['jd']) > max_jdtimediff:
            self.logger.debug("Data was taken at different times")
            return False
        return True

    def color_estimation(self, color1, color2, max_jdtimediff=1):
        cd1, cd2 = self.colordict[color1], self.colordict[color2]
        self.logger.info("Color of ({0},{1})".format(cd1, cd2))
        colorresult = dict()
        f1, f2 = color1, color2
        df1, df2 = self.data_filter[f1], self.data_filter[f2]
        # Match julian_dates from the two groups
        valid_pairs = \
            [pair for pair in itertools.product(df1, df2) \
             if self.is_valid_pair_for_color(pair[0], pair[1], max_jdtimediff)]

        if len(valid_pairs) == 0: return (None)
        pairs = dict()
        pairs[f1], pairs[f2] = np.transpose(valid_pairs)

        jds_val = np.asarray([(p1['jd'] + p2['jd']) / 2. \
                              for (p1, p2) in zip(pairs[f1], pairs[f2])])
        jds_err = np.asarray([abs(p1['jd'] - p2['jd']) / 2. \
                              for (p1, p2) in zip(pairs[f1], pairs[f2])])
        color_val = np.asarray([(p1['magpsf'] - p2['magpsf']) \
                                for (p1, p2) in zip(pairs[f1], pairs[f2])])
        color_err = np.asarray([np.sqrt(p1['sigmapsf'] ** 2 + p2['sigmapsf'] ** 2) \
                                for (p1, p2) in zip(pairs[f1], pairs[f2])])

        # is it significantly bluer?
        is_last = np.max(jds_val) == jds_val
        mean_color = np.mean(color_val[:-1])
        last_color = color_val[is_last][0]
        last_color_err = color_err[is_last][0]

        # return a dict with results
        colorresult['quantity'] = 'color'
        colorresult['label'] = '{0}-{1}'.format(cd1, cd2)
        colorresult['jds_val'] = jds_val
        colorresult['jds_err'] = jds_err
        colorresult['color_ave'] = \
            np.mean([item['magpsf'] for item in self.data_filter[f1]]) - \
            np.mean([item['magpsf'] for item in self.data_filter[f2]])
        colorresult['color_val'] = color_val
        colorresult['color_err'] = color_err
        # fit to a polynom of 1st or 2nd degreee
        coef, chi2 = self.iterative_polymodelfit(x=jds_val, y=color_val)
        colorresult['poly_coef'], colorresult['poly_chi2'] = coef, chi2
        # check the color
        colorresult['is_bluer'] = last_color + last_color_err < mean_color
        self.results[colorresult['label']] = colorresult
        return colorresult

    def run(self, light_curve=None, run_config=None):
        """ 
        ! TODO: UPDATE OUTDATED DOCSTRING !
        ***********************************

        'light_curve': instance of ampel.base.LightCurve. See LightCurve docstring for more info.
        'run_config': dict instance containing run parameters defined in ampel config section:
            max_order: maximum polynomic order to try
            calculate_color: True/False, boolean to indicate whether to compute color indices or not
        This method must return either:
            * A dict instance containing the values to be saved into the DB
                -> IMPORTANT: the dict *must* be BSON serializable, that is:
                    import bson
                    bson.BSON.encode(<dict instance to be returned>)
                must not throw a InvalidDocument Exception
            * One of these T2RunStates flag member:
                MISSING_INFO:  reserved for a future ampel extension where 
                               T2s results could depend on each other
                BAD_CONFIG:    Typically when run_config is not set properly
                ERROR:         Generic error
                EXCEPTION:     An exception occured
        """

        self.run_config = self.base_config if run_config is None else run_config
        self.min_jd = np.min(light_curve.get_values('jd'))
        self.max_jd = np.max(light_curve.get_values('jd'))
        self.classify_in_filters(light_curve)

        for color in self.available_colors:
            self.photometry_estimation(color)

        if self.run_config['calculate_color'] is True:
            for (color1, color2) in itertools.combinations(self.available_colors, 2):
                self.color_estimation(color1, color2, max_jdtimediff=1)

        return self.results
