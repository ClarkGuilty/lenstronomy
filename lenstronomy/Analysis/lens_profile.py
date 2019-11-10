import numpy as np
from lenstronomy.Util import util
from lenstronomy.Util import mask as mask_util
import lenstronomy.Util.multi_gauss_expansion as mge
from lenstronomy.Util import analysis_util


class LensProfileAnalysis(object):
    """
    class with analysis routines to compute derived properties of the lens model
    """
    def __init__(self, lens_model):
        """

        :param lens_model: LensModel instance
        """
        self._lens_model = lens_model

    def effective_einstein_radius(self, kwargs_lens, center_x=None, center_y=None, model_bool_list=None, grid_num=200,
                                  grid_spacing=0.05, get_precision=False, verbose=True):
        """
        computes the radius with mean convergence=1

        :param kwargs_lens: list of lens model keyword arguments
        :param spacing: number of annular bins to compute the convergence (resolution of the Einstein radius estimate)
        :param get_precision: If `True`, return the precision of estimated Einstein radius
        :return: estimate of the Einstein radius
        """
        center_x, center_y = analysis_util.profile_center(kwargs_lens, center_x, center_y)

        x_grid, y_grid = util.make_grid(numPix=grid_num, deltapix=grid_spacing)
        x_grid += center_x
        y_grid += center_y
        kappa = self._lens_model.kappa(x_grid, y_grid, kwargs_lens, k=model_bool_list)
        if self._lens_model.lens_model_list[0] in ['INTERPOL', 'INTERPOL_SCALED']:
            center_x = x_grid[kappa == np.max(kappa)]
            center_y = y_grid[kappa == np.max(kappa)]
        kappa = util.array2image(kappa)
        r_array = np.linspace(0, grid_num*grid_spacing/2., grid_num*2)
        for r in r_array:
            mask = np.array(1 - mask_util.mask_center_2d(center_x, center_y, r, x_grid, y_grid))
            sum_mask = np.sum(mask)
            if sum_mask > 0:
                kappa_mean = np.sum(kappa*mask)/np.sum(mask)
                if kappa_mean < 1:
                    if get_precision:
                        return r, r_array[1] - r_array[0]
                    else:
                        return r
        if verbose:
            Warning("No Einstein radius computed for the following model!", kwargs_lens)
        return np.nan

    def local_lensing_effect(self, kwargs_lens, ra_pos=0, dec_pos=0, model_list_bool=None):
        """
        computes deflection, shear and convergence at (ra_pos,dec_pos) for those part of the lens model not included
        in the main deflector.

        :param kwargs_lens: lens model keyword argument list
        :param ra_pos: RA position where to compute the external effect
        :param dec_pos: DEC position where to compute the external effect
        :param model_list_bool: boolean list indicating which models effect to be added to the estimate
        :return: alpha_x, alpha_y, kappa_ext, shear1, shear2
        """
        f_x, f_y = self._lens_model.alpha(ra_pos, dec_pos, kwargs_lens, k=model_list_bool)
        f_xx, f_xy, f_yx, f_yy = self._lens_model.hessian(ra_pos, dec_pos, kwargs_lens, k=model_list_bool)
        kappa_ext = (f_xx + f_yy)/2.
        shear1 = 1./2 * (f_xx - f_yy)
        shear2 = f_xy
        return f_x, f_y, kappa_ext, shear1, shear2

    def profile_slope(self, kwargs_lens, model_list_bool=None, num_points=10, verbose=True):
        """
        computes the logarithmic power-law slope of a profile

        :param kwargs_lens: lens model keyword argument list
        :param model_list_bool: bool list, indicate which part of the model to consider
        :param num_points: number of estimates around the Einstein radius
        :return: logarithmic power-law slope
        """
        theta_E = self.effective_einstein_radius(kwargs_lens, verbose=verbose)
        if np.isnan(theta_E):
            if verbose:
                print("Could not compute effective slope, because of Einstein radius")
            return np.nan
        x0 = kwargs_lens[0]['center_x']
        y0 = kwargs_lens[0]['center_y']
        x, y = util.points_on_circle(theta_E, num_points)
        dr = 0.01
        x_dr, y_dr = util.points_on_circle(theta_E + dr, num_points)

        alpha_E_x_i, alpha_E_y_i = self._lens_model.alpha(x0 + x, y0 + y, kwargs_lens, k=model_list_bool)
        alpha_E_r = np.sqrt(alpha_E_x_i**2 + alpha_E_y_i**2)
        alpha_E_dr_x_i, alpha_E_dr_y_i = self._lens_model.alpha(x0 + x_dr, y0 + y_dr, kwargs_lens, k=model_list_bool)
        alpha_E_dr = np.sqrt(alpha_E_dr_x_i ** 2 + alpha_E_dr_y_i ** 2)
        slope = np.mean(np.log(alpha_E_dr / alpha_E_r) / np.log((theta_E + dr) / theta_E))
        gamma = -slope + 2
        return gamma

    def radial_lens_profile(self, r_list, kwargs_lens, center_x=None, center_y=None, model_bool_list=None):
        """

        :param r_list: list of radii to compute the spherically averaged lens light profile
        :param center_x: center of the profile
        :param center_y: center of the profile
        :param kwargs_lens: lens parameter keyword argument list
        :param model_bool_list: bool list or None, indicating which profiles to sum over
        :return: flux amplitudes at r_list radii spherically averaged
        """
        center_x, center_y = analysis_util.profile_center(kwargs_lens, center_x, center_y)
        kappa_list = []
        for r in r_list:
            x, y = util.points_on_circle(r, num_points=20)
            f_r = self._lens_model.kappa(x + center_x, y + center_y, kwargs=kwargs_lens, k=model_bool_list)
            kappa_list.append(np.average(f_r))
        return kappa_list

    def multi_gaussian_lens(self, kwargs_lens, center_x=None, center_y=None, model_bool_list=None, n_comp=20):
        """
        multi-gaussian lens model in convergence space

        :param kwargs_lens:
        :param n_comp:
        :return:
        """
        center_x, center_y = analysis_util.profile_center(kwargs_lens, center_x, center_y)
        theta_E = self.effective_einstein_radius(kwargs_lens)
        r_array = np.logspace(-4, 2, 200) * theta_E
        kappa_s = self.radial_lens_profile(r_array, kwargs_lens, center_x=center_x, center_y=center_y,
                                                model_bool_list=model_bool_list)
        amplitudes, sigmas, norm = mge.mge_1d(r_array, kappa_s, N=n_comp)
        return amplitudes, sigmas, center_x, center_y

    def mass_fraction_within_radius(self, kwargs_lens, center_x, center_y, theta_E, numPix=100):
        """
        computes the mean convergence of all the different lens model components within a spherical aperture

        :param kwargs_lens: lens model keyword argument list
        :param center_x: center of the aperture
        :param center_y: center of the aperture
        :param theta_E: radius of aperture
        :return: list of average convergences for all the model components
        """
        x_grid, y_grid = util.make_grid(numPix=numPix, deltapix=2.*theta_E / numPix)
        x_grid += center_x
        y_grid += center_y
        mask = mask_util.mask_sphere(x_grid, y_grid, center_x, center_y, theta_E)
        kappa_list = []
        for i in range(len(kwargs_lens)):
            kappa = self._lens_model.kappa(x_grid, y_grid, kwargs_lens, k=i)
            kappa_mean = np.sum(kappa * mask) / np.sum(mask)
            kappa_list.append(kappa_mean)
        return kappa_list

    def convergence_peak(self, kwargs_lens, k=None, model_bool_list=None, grid_num=200, grid_spacing=0.01, center_x_init=0, center_y_init=0):
        """
        computes the maximal convergence position on a grid and returns its coordinate

        :param kwargs_lens: lens model keyword argument list
        :param model_bool_list: bool list (optional) to include certain models or not
        :return: center_x, center_y
        """
        x_grid, y_grid = util.make_grid(numPix=grid_num, deltapix=grid_spacing)
        x_grid += center_x_init
        y_grid += center_y_init

        kappa = self._lens_model.kappa(x_grid, y_grid, kwargs_lens, k=model_bool_list)

        center_x = x_grid[kappa == np.max(kappa)]
        center_y = y_grid[kappa == np.max(kappa)]
        return center_x, center_y
