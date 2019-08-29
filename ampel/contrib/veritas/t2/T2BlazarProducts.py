from ampel.base.abstract.AbsT2Unit import AbsT2Unit
import astropy.stats as astats
from astropy.time import Time
import datetime
import logging
import numpy as np
import itertools


# from ampel.abstract.AbsT2Unit import AbsT2Unit

def numpy_to_std_types(dict_object):
    # Convert everything back to std types to allow serialization
    for item in dict_object:
        if type(dict_object[item]) == np.ndarray:
            dict_object[item] = dict_object[item].tolist()
        elif type(dict_object[item]) == np.bool_:
            dict_object[item] = bool(dict_object[item])
        elif type(dict_object[item]) == np.float64:
            dict_object[item] = float(dict_object[item])
        elif type(dict_object[item]) == np.int:
            dict_object[item] = int(dict_object[item])
    return(dict_object)

class T2BlazarProducts(AbsT2Unit):
    version = 1.0
    author = "mireia.nievas-rosillo@desy.de"
    private = False
    upperLimits = False

    default_config = {
        'max_order': 2,
        'calculate_color': True,
        'bblocks_p0': 0.05
    }

    def __init__(self, logger=None, base_config=None):
        """
        ***********************************
        ':param logger': instance of logging.Logger (std python module 'logging')
            -> example usage: logger.info("this is a log message")
        ':param base_config': optio+nal dict loaded from ampel config section.
        """

        # Save the logger as instance variable
        super().__init__(logger)
        self.logger = logger if logger is not None else logging.getLogger()
        self.base_config = self.default_config if base_config is None else base_config
        self.colordict = {1: 'g', 2: 'r', 3: 'i'}  # i is not really used
        
    def clear_results(self):
        # Clear variables
        self.run_config       = None
        self.data_filter      = dict()
        self.uls_filter       = dict()
        self.results          = dict()
        self.available_photom = list()
        self.available_colors = list()

    def get_current_and_future_jd(self):
        #Get current julian date and next day/week
        self.jd_now      = Time(datetime.datetime.now()).jd
        self.jd_nextday  = self.jd_now+1
        self.jd_nextweek = self.jd_now+7

    def classify_in_filters(self,light_curve):
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

        self.available_bands = sorted(list(self.data_filter.keys()))

    def iterative_polymodelfit(self, x, y):
        '''
        Performs iterative polynomial fit with increasing order checking the chi2.
        :param x: x-axis data
        :param y: y-data to fit
        The maximum order can be tuned through the parameter
        self.run_config['max_order']
        :return: Returns best-fitting polynomial paramaters and the chi2.
        '''
        self.logger.info("Performing a polynomial fit of the data")
        if len(y) < 3:
            return (None, None)
        poly, res = np.polyfit(x, y, 0, full=True)[0:2]
        if res == None:
            return (None, None)
        
        chisq_dof = (res / (len(x) - 1))[0]
        for k in range(1,self.run_config['max_order']+1):
            if len(y) > k + 2:
                self.logger.debug("Trying poly({0}) shape".format(k))
                poly_new, res_new = np.polyfit(x, y, k, full=True)[0:2]
                if len(res_new) == 0: break
                chisq_dof_new = (res_new / (len(x) - (k + 1)))[0]
                if chisq_dof_new < chisq_dof * 0.8:
                    poly, res = poly_new, res_new
                    chisq_dof = chisq_dof_new
        return (poly, chisq_dof)

    def estimate_bayesian_blocks(self, x, y, yerr):
        '''
        :param x: x-data points (typically JD dates)
        :param y: y-data points (typically mag/fluxes)
        :param yerr: y-data errors (in the same units
        :return: bayesianblocks dict with the x values,
                 the xerr (extension of the block) and
                 y/yerr (weighted average and errors).
        '''
        # make sure we have have numpy arrays
        x = np.asarray(x)
        y = np.asarray(y)
        yerr = np.asarray(yerr)
        # just in case it is needed, remove repeated x-data
        x,_indices = np.unique(x,return_index=True)
        y = y[_indices]
        yerr = yerr[_indices]

        # false alarm probability
        p0 = self.run_config['bblocks_p0']
        edges = astats.bayesian_blocks(x, y, yerr, fitness='measures', p0=p0)
        bayesianblocks = {'x': [], 'xerr': [], 'y': [], 'yerr': []}
        for xmin, xmax in zip(edges[:-1], edges[1:]):
            filt = (x >= xmin) * (x < xmax)
            if np.sum(filt) == 0: continue
            xave = (xmin + xmax) / 2.
            xerr = (xmax - xmin) / 2.
            yave = np.average(y[filt], weights=1. / yerr[filt] ** 2)
            ystd = (np.sum(1. / yerr[filt] ** 2)) ** (-1. / 2)
            bayesianblocks['x'].append(xave)
            bayesianblocks['xerr'].append(xerr)
            bayesianblocks['y'].append(yave)
            bayesianblocks['yerr'].append(ystd)
        return (bayesianblocks)

    def photometry_estimation(self, color):
        '''
        Collects photometry for the specified band performs an iterative model fit.
        :param color: photometric band (V, R)
        :return: dictionary containing photometry.
        '''
        cfilt = self.colordict[color]   # current filter color
        cdata = self.data_filter[color] # current filter data
        self.logger.info("Photometry of filter {0}".format(cfilt))
        photresult = dict()
        # Normal values
        photresult['jds_val'] = np.asarray([item['jd'] for item in cdata])
        photresult['jds_err'] = np.asarray([0 for item in cdata])
        photresult['mag_val'] = np.asarray([item['magpsf'] for item in cdata])
        photresult['mag_err'] = np.asarray([item['sigmapsf'] for item in cdata])

        # Upper limits
        try:             cdata = self.uls_filter[color]
        except KeyError: cdata = []
        photresult['uls_jds_val'] = np.asarray([item['jd'] for item in cdata])
        photresult['uls_jds_err'] = np.asarray([0 for item in cdata])
        photresult['uls_mag']      = np.asarray([item['diffmaglim'] for item in cdata])
        
        photresult['quantity'] = 'mag'
        photresult['label']    = 'phot_mag_{0}'.format(cfilt)
        # check if the source is becoming significantly brighter
        mean_mag     = np.mean(photresult['mag_val'])
        mean_mag_err = np.std(photresult['mag_val'])
        last_mag     = photresult['mag_val'][-1]
        last_mag_err = photresult['mag_err'][-1]
        # Get the bayesian blocks
        photresult['bayesian_blocks'] = self.estimate_bayesian_blocks( \
            x=photresult['jds_val'],
            y=photresult['mag_val'],
            yerr=photresult['mag_err'])
        # is_brighter  = last_mag+last_mag_err<mean_mag-mean_mag_err
        is_brighter = int(last_mag + last_mag_err < mean_mag)
        photresult['is_brighter'] = is_brighter
        # Fit the trend by a polynomium of degree 2,3 or 4
        coef, chi2 = self.iterative_polymodelfit(\
            x=photresult['jds_val'], y=photresult['mag_val'])
        if (coef is not None):
            photresult['poly_coef'], photresult['poly_chi2'] = coef, chi2
            polyfit = np.poly1d(photresult['poly_coef'])
            photresult['trend_1d'] = \
                polyfit(self.jd_nextday) < polyfit(self.jd_now)
            photresult['trend_1w'] = \
                polyfit(self.jd_nextweek) < polyfit(self.jd_now)
        else:
            photresult['trend_1d']    = False
            photresult['trend_1w']    = False
            photresult['is_brighter'] = False

        # Convert everything back to std types to allow serialization
        photresult = numpy_to_std_types(photresult)

        self.results[photresult['label']] = photresult
        if photresult['label'] not in self.available_photom:
            self.available_photom.append(photresult['label'])
        
        return (photresult)

    def is_valid_pair_for_color(self, item1, item2, max_jdtimediff=1):
        '''
        Checks if a pair of alerts are close enough in time to compute e.g. colors.
        :param item1: alert object
        :param item2: alert object
        :param max_jdtimediff: maximum time difference (in days) allowed.
        :return: True/False
        '''
        if item1['fid'] == item2['fid']:
            self.logger.debug("Data was taken with the same filter")
            return False
        if abs(item1['jd'] - item2['jd']) > max_jdtimediff:
            self.logger.debug("Data was taken at different times")
            return False
        return (True)

    def color_estimation(self, color1, color2, max_jdtimediff=1):
        '''
        Computes color (band1-band2)
        :param color1: 1st photometric filter/band (e.g. V)
        :param color2: 2nd photometric filter/band (e.g. R)
        :param max_jdtimediff: maximum time difference (in days) allowed.
        :return: dictionary containing the color photometry.
        '''
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
        mean_color     = np.mean(color_val)
        mean_color_err = np.std(color_val)
        last_color     = color_val[-1]
        last_color_err = color_err[-1]

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
        # fit to a polynom of 3rd degreee
        coef, chi2 = self.iterative_polymodelfit(x=jds_val, y=color_val)
        # Get the bayesian blocks
        colorresult['bayesian_blocks'] = self.estimate_bayesian_blocks( \
            x=colorresult['jds_val'],
            y=colorresult['color_val'],
            yerr=colorresult['color_err'])
        
        # check the color w.r.t to historical values
        if (coef is not None):
            colorresult['poly_coef'], colorresult['poly_chi2'] = coef, chi2
            polyfit = np.poly1d(colorresult['poly_coef'])
            colorresult['trend_1d'] = \
                polyfit(self.jd_nextday) < \
                polyfit(self.jd_now)
            colorresult['trend_1w'] = \
                polyfit(self.jd_nextweek) < \
                polyfit(self.jd_now)
            # check the color
            colorresult['is_bluer'] = last_color + last_color_err < mean_color
        else:
            colorresult['trend_1d'] = False
            colorresult['trend_1w'] = False
            colorresult['is_bluer'] = False

        # Convert everything back to std types to allow serialization
        colorresult = numpy_to_std_types(colorresult)

        self.results[colorresult['label']] = colorresult
        if colorresult['label'] not in self.available_colors:
            self.available_colors.append(colorresult['label'])
        return (colorresult)

    def estimate_excitement(self):
        '''
        check variables to assess how exciting the alert is
        :return: None (fills the self.results['excitement'] property.
        '''
        # check variables to assess how exciting the alert is
        max_score:  float = 0.
        excitement: float = 0.
        # Check for changes in color. If the source is becoming bluer,
        # it potentially means that the Sync. peak is moving to higher freqs.
        # in case of blazars, that could lead to enhanced VHE emission.
        # Two ways:
        # - Check if the last point is bluer than the average
        # - Check the trend (polyfit)
        # - TODO: additional test with the bayesian blocks??
        for color in  self.available_colors:
            max_score += 4
            if self.results[color]['is_bluer'] == True:
                # Source is becoming bluer (Sync. peak moving to the right, promising).
                excitement += 1
            if self.results[color]['trend_1w'] == True:
                # Source is becoming bluer (Sync. peak moving to the right, promising).
                excitement += 1
            if self.results[color]['trend_1d'] == True:
                # Source is becoming bluer (Sync. peak moving to the right, promising).
                excitement += 1
            bayesianblocks = self.results[color]['bayesian_blocks']
            if len(bayesianblocks['x'])>1:
                if bayesianblocks['y'][-1] < bayesianblocks['y'][-2]:
                    excitement += 1
        # Check for changes in brightness in different filters.
        # Brighter potentially means more injected electrons -> enhanced SSC / EC emission.
        # Two ways:
        # - Check if the last point is brighter than the average
        # - Check the trend (polyfit)
        # - TODO: additional test with the bayesian blocks??
        for band in self.available_photom:
            max_score += 4
            if self.results[band]['is_brighter'] == True:
                excitement += 1
            if self.results[band]['trend_1w'] == True:
                excitement += 1
            if self.results[band]['trend_1d'] == True:
                excitement += 1
            bayesianblocks = self.results[band]['bayesian_blocks']
            if len(bayesianblocks['x'])>1:
                if bayesianblocks['y'][-1] < bayesianblocks['y'][-2]:
                    excitement += 1
        
        self.results['excitement'] = excitement * 1. / max_score

        return(self.results['excitement'])

    def run(self, light_curve=None, run_config=None):
        """
        ! TODO: UPDATE OUTDATED DOCSTRING !
        ***********************************

        'light_curve': instance of ampel.base.LightCurve. See LightCurve docstring for more info.
        'run_config': dict instance containing run parameters defined in ampel config section:
            t2_run_config->POLYFIT_[run_config_id]->runConfig
            whereby the run_config_id value is defined in the associated t2 document.
            In the case of POLYFIT, run_config_id would be either 'default' or 'advanced'.
            A given channel (say HU_SN_IA) could use the runConfig 'default' whereas
            another channel (say OKC_SNIIP) could use the runConfig 'advanced'
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

        self.clear_results()
        self.run_config = run_config if run_config is not None else self.base_config
        self.min_jd = np.min(light_curve.get_values('jd'))
        self.max_jd = np.max(light_curve.get_values('jd'))
        self.classify_in_filters(light_curve)
        self.get_current_and_future_jd()

        for color in self.available_bands:
            self.photometry_estimation(color)

        for (color1, color2) in itertools.combinations(self.available_bands, 2):
            self.color_estimation(color1, color2, max_jdtimediff=1)

        self.estimate_excitement()

        return self.results

