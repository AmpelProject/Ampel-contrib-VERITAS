from ampel.base.abstract.AbsT2Unit import AbsT2Unit
import numpy as np
import itertools
from pydantic import BaseModel
#from ampel.abstract.AbsT2Unit import AbsT2Unit

class T2BlazarProducts():
    
    version = 1.0
    author = "mireia.nievas-rosillo@desy.de"
    private = False
    upperLimits = False

    class RunConfig(BaseModel):
        """ validate the configuration """
        max_order        : int   = 2   
	
    def __init__(self, logger=None, run_config=None):
        """

        ! TODO: UPDATE OUTDATED DOCSTRING !
        ***********************************

        'logger': instance of logging.Logger (std python module 'logging')
            -> example usage: logger.info("this is a log message")
        'base_config': optional dict loaded from ampel config section: 
            t2_units->POLYFIT->baseConfig
        """

        # Save the logger as instance variable
        self.logger = logger if logger is not None else logging.getLogger()
        self.results = dict()
        
    def classify_in_filters(self,light_curve):
        self.colordict = {1:'g',2:'r',3:'i'} # i is not really used
        self.data_filter = {}
        for item in light_curve.ppo_list:
            #item['mjd'] = item['jd']-2400000.5
            if item.get_value('fid') not in self.data_filter:
                self.data_filter[item.get_value('fid')] = []
            self.data_filter[item.get_value('fid')].append(item.content)
        
        self.uls_filter = {}
        for item in light_curve.ulo_list:
            #item['mjd'] = item['jd']-2400000.5
            if item.get_value('fid') not in self.uls_filter:
                self.uls_filter[item.get_value('fid')] = []
            self.uls_filter[item.get_value('fid')].append(item.content)
        
        self.available_colors = sorted(list(self.data_filter.keys()))
    
    def iterative_polymodelfit(self,x,y):
        self.logger.info("Performing a polynomial fit of the data")
        if len(y) < 3:
            return(None,None)
        poly,res,_,_,_ = np.polyfit(x,y,1,full=True)
        chisq_dof = (res / (len(x)-2))[0]
        for k in range(3):
            if len(y)>k+3:
                self.logger.debug("Trying poly({0}) shape".format(k+2))
                poly_new,res_new,_,_,_ = np.polyfit(x,y,k+2,full=True)
                if len(res_new) == 0: break
                chisq_dof_new = (res_new / (len(x)-(k+3)))[0]
                if chisq_dof_new < chisq_dof*0.8:
                    poly,res  = poly_new,res_new
                    chisq_dof = chisq_dof_new
        return(poly,chisq_dof)
    
    def photometry_estimation(self,color):
        cthis = self.colordict[color]
        self.logger.info("Photometry of filter {0}".format(cthis))
        photresult = dict()
        cit   = self.data_filter[color]
        photresult['jds_val']  = np.asarray([item['jd']       for item in cit])
        photresult['jds_err']  = np.asarray([0                for item in cit])
        photresult['mag_val']  = np.asarray([item['magpsf']   for item in cit])
        photresult['mag_err']  = np.asarray([item['sigmapsf'] for item in cit])
        # uls
        cit   = self.uls_filter[color]
        photresult['uls_jds_val'] = np.asarray([item['jd']       for item in cit])
        photresult['uls_jds_err'] = np.asarray([0                for item in cit])
        photresult['uls_mag']     = np.asarray([item['diffmaglim']   for item in cit])
        
        photresult['quantity'] = 'mag'
        photresult['label']    = 'phot_mag_{0}'.format(cthis)
        # check if the source is becoming significantly brighter
        mean_mag     = np.mean(photresult['mag_val'][:-1])
        mean_mag_err = np.std(photresult['mag_val'][:-1])
        last_mag     = photresult['mag_val'][-1]
        last_mag_err = photresult['mag_err'][-1]
        is_brighter  = last_mag+last_mag_err<mean_mag-last_mag_err
        photresult['is_brighter'] = is_brighter
        # Fit the trend by a polynomium of degree 2,3 or 4
        coef,chi2 = self.iterative_polymodelfit(\
          x=photresult['jds_val'], y=photresult['mag_val'])
        photresult['poly_coef'],photresult['poly_chi2'] = coef,chi2 
        # append everything
        self.results[photresult['label']] = photresult
        return(photresult)
    
    def is_valid_pair_for_color(self,item1,item2,max_jdtimediff=1):
        if item1['fid'] == item2['fid']:
            self.logger.debug("Data was taken with the same filter")
            return False
        if abs(item1['jd']-item2['jd']) > max_jdtimediff:
            self.logger.debug("Data was taken at different times")
            return False
        return(True)
    
    def color_estimation(self,color1,color2,max_jdtimediff=1):
        cd1,cd2 = self.colordict[color1],self.colordict[color2]
        self.logger.info("Color of ({0},{1})".format(cd1,cd2))
        colorresult = dict()
        f1,f2   = color1,color2
        df1,df2 = self.data_filter[f1],self.data_filter[f2]
        # Match julian_dates from the two groups
        valid_pairs = \
          [pair for pair in itertools.product(df1,df2) \
           if self.is_valid_pair_for_color(pair[0],pair[1],max_jdtimediff)]
        
        if len(valid_pairs) == 0: return(None)
        pairs = dict()
        pairs[f1],pairs[f2] = np.transpose(valid_pairs)
        

        jds_val   = np.asarray([(p1['jd']+p2['jd'])/2. \
                      for (p1,p2) in zip(pairs[f1],pairs[f2])])
        jds_err   = np.asarray([abs(p1['jd']-p2['jd'])/2. \
                      for (p1,p2) in zip(pairs[f1],pairs[f2])])
        color_val = np.asarray([(p1['magpsf']-p2['magpsf']) \
                      for (p1,p2) in zip(pairs[f1],pairs[f2])])
        color_err = np.asarray([np.sqrt(p1['sigmapsf']**2+p2['sigmapsf']**2) \
                      for (p1,p2) in zip(pairs[f1],pairs[f2])])

        # is it significantly bluer?
        is_last = np.max(jds_val)==jds_val
        mean_color = np.mean(color_val[:-1])
        last_color = color_val[is_last][0]
        last_color_err = color_err[is_last][0]

        # return a dict with results
        colorresult['quantity']= 'color'
        colorresult['label']   = '{0}-{1}'.format(cd1,cd2)
        colorresult['jds_val'] = jds_val
        colorresult['jds_err'] = jds_err
        colorresult['color_ave'] = \
          np.mean([item['magpsf'] for item in self.data_filter[f1]])-\
          np.mean([item['magpsf'] for item in self.data_filter[f2]])
        colorresult['color_val'] = color_val
        colorresult['color_err'] = color_err
        # fit to a polynom of 3rd degreee
        coef,chi2 = self.iterative_polymodelfit(x=jds_val,y=color_val)
        colorresult['poly_coef'],colorresult['poly_chi2'] = coef, chi2
        # check the color
        colorresult['is_bluer']  = last_color+last_color_err<mean_color
        self.results[colorresult['label']] = colorresult
        return(colorresult)
    
    def plot_trend(self,dictplot,fit=False,fig=None,ax=None,color='k'):
        
        is_last = np.max(dictplot['jds_val'])==dictplot['jds_val']        
        xval = Time(dictplot['jds_val'],format='jd')
        xerr = dictplot['jds_err']
        yval = dictplot['{0}_val'.format(dictplot['quantity'])]
        yerr = dictplot['{0}_err'.format(dictplot['quantity'])]
        
        mean_val = np.mean(yval)
        
        ######### Get the figure and axis, create them if they do not exist
        if fig is not None:
            self.fig = fig
        else:
            self.fig = plt.figure(figsize=(6,2.2))
            ax = self.fig.add_subplot(111)
        if ax is None:
            ax = plt.gca()
        
        ####### Plot non detections
        try:
            xval_uls = Time(dictplot['uls_jds_val'],format='jd')
            yval_uls = dictplot['uls_{0}'.format(dictplot['quantity'])]
            ax.errorbar(
                x    = xval_uls.datetime,
                y    = yval_uls,
                yerr = -0.3,
                uplims = True,
                ls='None', ms=3, mfc='white',
                color=color, marker='D')
        except KeyError:
            # no uls to plot
            pass
        
        ####### Plot the detections (remark the last one)
        if len(is_last)>1:
            ax.errorbar(
                x    = xval[~is_last].datetime,
                #xerr = xerr[~is_last],
                y    = yval[~is_last],
                yerr = yerr[~is_last],
                ls='None', ms=3, mfc='white',
                color=color, marker='D', 
                label='previous data')
        ax.errorbar(
            x    = xval[is_last].datetime,
            #xerr = xerr[is_last],
            y    = yval[is_last],
            yerr = yerr[is_last],
            ls='None', ms=3, mfc=color,
            color='black', marker='D', 
            label='last value')

        ####### Plot the current trend.
        if fit and dictplot['poly_coef'] is not None:
            # Evaluate the polynom
            x_fit = np.linspace(np.min(xval),np.max(xval),20)
            polyfit = np.poly1d(dictplot['poly_coef'])
            ax.plot(Time(x_fit,format='jd').datetime, 
                    polyfit(x_fit),lw=1,color=color)
        
        ####### Average values 
        ax.hlines(mean_val,
                  xmin=np.min(xval.datetime),
                  xmax=np.max(xval.datetime),
                  color=color,zorder=-10,
                  lw=1,linestyles='dotted',
                  label='average')
        
        ax.set_ylabel(dictplot['label'])
        ax.legend(fontsize='x-small',ncol=3)
        
        ax.tick_params(axis='x', rotation=20)
        #ax.set_xlim(Time(self.min_jd-1,format='jd').datetime,
        #            Time(self.max_jd+1,format='jd').datetime)
        
        yearsFmt = mdates.DateFormatter('%Y/%m/%d')
        ax.xaxis.set_major_formatter(yearsFmt)
        ax.xaxis.set_major_locator(ticker.MultipleLocator(3))
        
        # Invert Y-axis
        #ax.set_ylim(ax.get_ylim()[::-1])
        
        fig.suptitle('Light curve',fontsize=12,y=1.01)

        ax.grid(True,ls='dashed',lw=0.5)
        plt.tight_layout()
        plt.close()
        
        self.results['fig'] = fig
        
        return(self.fig)
    
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
        
        self.min_jd = np.min(light_curve.get_values('jd'))
        self.max_jd = np.max(light_curve.get_values('jd'))
        self.classify_in_filters(light_curve)
        
        self.figure = plt.figure(figsize=(6,4.2))
        subplot_phot  = self.figure.add_subplot(2,1,1)
        subplot_color = self.figure.add_subplot(2,1,2,sharex=subplot_phot)
        
        for color in self.available_colors:
            photresult = self.photometry_estimation(color)
            if photresult is None: continue
            self.figure = self.plot_trend(photresult,
                fig=self.figure,ax=subplot_phot,
                color=self.colordict[color],fit=True)
        
        for (color1,color2) in itertools.combinations(\
            self.available_colors,2):
            colorresult=self.color_estimation(\
                    color1,color2,max_jdtimediff=1)
            if colorresult is None: continue
            self.figure = self.plot_trend(colorresult,
                fig=self.figure,ax=subplot_color,
                color=self.colordict[color],fit=True)
        
        ### Revert photometric magnitude y-axis.
        subplot_phot.set_ylim(subplot_phot.get_ylim()[1]*1.05,
                              subplot_phot.get_ylim()[0]*0.95)
        
        
        return(self.results)
            
    
