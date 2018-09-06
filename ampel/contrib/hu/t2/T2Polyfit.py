#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File              : ampel/contrib/hu/t2/T2SNCosmo.py
# License           : BSD-3-Clause
# Author            : j.nordin <jnordin@physik.hu-berlin.de>
# Date              : 04.09.2018
# Last Modified Date: 04.09.2018
# Last Modified By  : j.nordin <jnordin@physik.hu-berlin.de>

import numpy as np
from ampel.base.abstract.AmpelABC import AmpelABC, abstractmethod
from ampel.base.abstract.AbsT2Unit import AbsT2Unit
from ampel.core.flags.T2RunStates import T2RunStates

VERSION = 0.1


################################
#                              #
#     To Be Made Global        #
#                              #
################################
ZTF_BANDPASSES = {1:{"name":"sdssg"},
                  2:{"name":"sdssr"},
                  3:{"name":"sdssi"},
                 }

def filter_id__to__bandpass_name(filter_id):
    """ """
    if type(filter_id) == int and filter_id in ZTF_BANDPASSES.keys():
        return ZTF_BANDPASSES[filter_id]["name"]
    return filter_id


################################
#                              #
#     Internal Tools           #
#                              #
################################
def mag_to_flux(mag, wavelength, magerr=None):
    """ converts magnitude into flux

    Parameters
    ----------
    mag: [float or array]
        AB magnitude(s)

    wavelength: [float or array]
        central wavelength of the photometric filter.
        In Angstrom

    magerr: [float or array] -optional-
        magnitude error if any

    Returns
    -------
    - float or array (if magerr is None)
    - float or array, float or array (if magerr provided)
    (flux are returned in erg/s/cm2/A)
    """
    flux = 10**(-(mag+2.406)/2.5) / wavelength**2
    if magerr is None:
        return flux
    
    dflux = np.abs(flux*(-magerr/2.5*np.log(10))) # df/f = dcount/count
    return flux,dflux

def get_bandpasses(bandnames):
    """ returns a dictionary with the given bandpasses """
    return {bandname:sncosmo.get_bandpass(bandname) for bandname in np.unique(np.atleast_1d(bandnames))}

################################
#                              #
#  sncosmo<-> Ampel Object     #
#                              #
################################

class SNCosmoTool:
    """ """
    def load_data(self, light_curve):
        """ extract sncosmo data from  Ampel's light_curve 
    
        Returns
        -------
        astropy Table
        """
        from astropy.table import Table
        filter_names = [filter_id__to__bandpass_name(fid) for fid in light_curve.get_values("fid")]
        # print(filter_names)
        bandpasses   = get_bandpasses(np.unique(filter_names))
        wavelengths  = [bandpasses[bp_].wave_eff for bp_ in filter_names]
        # - fluxes
        flux, fluxerr = np.asarray([mag_to_flux(mag_, lbda_, magerr_) for lbda_, mag_,magerr_ in 
                                    zip(wavelengths, light_curve.get_values("magpsf"),
                                        light_curve.get_values("sigmapsf")) ]).T
        
        self.sncosmo_data = Table( {"time": light_curve.get_values("obs_date"),
                       "flux": flux,
                       "fluxerr": fluxerr,
                       "band":filter_names,
                       "zp": [25]*len(filter_names),
                       "zpsys":["ab"]*len(filter_names)}
                    )





    
################################
#                              #
#     T2 Object                #
#                              #
################################
class T2Polyfit(AbsT2Unit):
    """
    Do numpy polyfit on specified band
    
    """
    version = VERSION
    
    def __init__(self, logger, base_config):
        """ """
        self.logger = logger
        
        self.base_config = {} if base_config is None else base_config
            
            
    # ==================== #
    # AMPEL T2 MANDATORY   #
    # ==================== #    
    def run(self, light_curve, run_parameters):
        """ 

        Parameters
        -----------
        light_curve: "ampel.base.LightCurve" instance. 
             See the LightCurve docstring for more info.

        run_parameters: dict containing run parameters defined in ampel config section:
            - bandID : [1,2,3]   # Id of ZTF filter fo fit
            - order : 1          # Order of linear fit

        Returns
        -------
        dict
        """
        
        # ------------- #
        #   Input       #
        # ------------- #
        model = run_parameters.pop("model",None)
        # - load the data
        sncosmo_tool = SNCosmoTool()
        sncosmo_tool.load_data(light_curve)

        # ------------- #
        #   LC Fit      #
        # ------------- #
        fit_kwargs = self.base_config if run_parameters is None else {**self.base_config, **run_parameters}
        
        if model in ["salt","Ia","ia","snia", "salt2","SALT2"]:
            if self.logger is not None: self.logger.info("Running T2SNcosmo with *salt2* model")
            #
            [result, fitted_model], kwargs_out = sncosmo_tool.fit_salt2(**fit_kwargs)
            #
        else:
            if self.logger is not None: self.logger.info("Only T2SNCosmo with config model:'Ia' has been implemented. You gave %s"%model)
            raise NotImplementedError("Only T2SNCosmo with config model:'Ia' has been implemented. You gave %s"%model)

        # ------------- #
        #   Output      #
        # ------------- #
        # = Structure the output
        fit_parameters = kwargs_out
        result_param = {}
        for i,pname in enumerate(result.param_names):
            result_param[pname]        = result["parameters"][i]
            result_param[pname+".err"] = result["errors"][pname]

        return {"sncosmo_info": {k: result[k] for k in ["success","chisq","ndof"]},
                "fit_lc_parameters": fit_parameters,
                "model_analysis": sncosmo_tool.get_results_analysis(result, model=model),
                "model":model,
                "fit_acceptable": bool(~np.any([ result['ndof']<-1 , result['chisq']/result['ndof']>3 or result['chisq']/result['ndof']<0.2, not result["success"]  ])) if result['ndof'] >0 else False,
                "fit_results":result_param
                }
