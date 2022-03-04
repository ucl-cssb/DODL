import numpy as np
import sys
import os

import helper_functions as hf
from plate import Plate
from species import Species
import math

def gompertz(t, A, um, lam):


    return A* np.exp(-np.exp((um*np.e)/A*(lam - t) +1))


def dgompertz(t, A, um, lam):
    return um * np.exp(um*(np.e*lam -np.e*t)/A - np.exp(um*(np.e*lam-np.e*t)/A +1) + 2) #1e8 to convert from OD to cells per grid point


def make_plate(receiver_coords, inducer_coords, params, inducer_conc, environment_size, w, dx, laplace = False, bandpass = False, fitting = False):


    amount = inducer_conc * 1e-6 #milli moles

    agar_thickness = 3.12  # mm

    init_conc = amount / (w ** 2 * agar_thickness) #mol/mm^3

    if fitting:
        init_conc /= len(inducer_coords)

    init_conc *= 1e6  # mM
    A_0 = init_conc

    D_N, mu_max, K_mu, gamma, D_A, \
    alpha_T, beta_T, K_IT, n_IT, K_lacT, T7_0, \
    alpha_R, beta_R, K_IR, n_IR, K_lacR, R_0, \
    alpha_G, beta_G, n_A, K_A, n_R, K_R, X_0, G_s = params

    ## Create our environment
    plate = Plate(environment_size)

    ## add one strain to the plate

    rows = receiver_coords[:, 0]
    cols = receiver_coords[:, 1]

    receiver_flags = np.zeros(environment_size)
    receiver_flags[rows,cols] = 1
    U_X = np.zeros(environment_size)
    U_X[rows, cols] = X_0

    strain = Species("X", U_X)
    def X_behaviour(t, species, params):
        ## unpack params

        #mu = mu_max * np.maximum(0, species['N']) / (K_mu + np.maximum(0, species['N'])) * np.maximum(0,species['X'])
        mu  = dx(t, species)*receiver_flags

        return mu
    strain.set_behaviour(X_behaviour)
    plate.add_species(strain)

    ## add IPTG to plate
    #inducer_position = [[int(j * (4.5/w)) for j in i] for i in inducer_positions  # convert position to specified dims

    U_A = np.zeros(environment_size)
    rows = inducer_coords[:, 0]
    cols = inducer_coords[:, 1]
    U_A[rows, cols] = A_0

    A = Species("A", U_A)
    def A_behaviour(t, species, params):
        ## unpack params
        D_N, mu_max, K_mu, gamma, D_A, \
        alpha_T, beta_T, K_IT, n_IT, K_lacT, T7_0, \
        alpha_R, beta_R, K_IR, n_IR, K_lacR, R_0, \
        alpha_G, beta_G, n_A, K_A, n_R, K_R, X_0, G_s = params

        a = D_A * hf.ficks(np.maximum(0,species['A']), w, laplace = laplace)
        return a
    A.set_behaviour(A_behaviour)
    plate.add_species(A)

    inducer_flags = np.zeros(environment_size)
    inducer_flags[rows, cols] = 2

    #plt.imshow(inducer_flags + receiver_flags)
    #plt.show()

    #add T7 to the plate
    U_T7 = np.ones(environment_size) * T7_0
    T7 = Species("T7", U_T7)
    def T7_behaviour(t, species, params):
        D_N, mu_max, K_mu, gamma, D_A, \
        alpha_T, beta_T, K_IT, n_IT, K_lacT, T7_0, \
        alpha_R, beta_R, K_IR, n_IR, K_lacR, R_0, \
        alpha_G, beta_G, n_A, K_A, n_R, K_R, X_0, G_s = params

        mu = dx(t, species)*receiver_flags

        dT7 = (alpha_T*mu*(1 + (np.maximum(0,species['A'])/K_IT)**n_IT))/(1 + (np.maximum(0,species['A'])/K_IT)**n_IT + K_lacT) + beta_T*mu - mu*np.maximum(0,species['T7'])


        return dT7
    T7.set_behaviour(T7_behaviour)
    plate.add_species(T7)

    ## add GFP to plate
    U_G = np.zeros(environment_size)
    G = Species("G", U_G)
    def G_behaviour(t, species, params):
        ## unpack params
        D_N, mu_max, K_mu, gamma, D_A, \
        alpha_T, beta_T, K_IT, n_IT, K_lacT, T7_0, \
        alpha_R, beta_R, K_IR, n_IR, K_lacR, R_0,\
        alpha_G, beta_G, n_A, K_A, n_R, K_R, X_0, G_s = params

        mu = dx(t, species)*receiver_flags
        T7 = np.maximum(0, species['T7'])

        if bandpass:
            R = np.maximum(0, species['R'])

        #R = 0  # produces treshold
        if bandpass:
            dGFP = alpha_G * mu * T7**n_A / (K_A**n_A + T7**n_A) * K_R**n_R / (K_R**n_R + R**n_R) + beta_G * mu - np.maximum(0, species['G']) * mu*G_s
        else:
            dGFP = alpha_G * mu * T7**n_A / (K_A**n_A + T7**n_A) + beta_G * mu - np.maximum(0, species['G']) * mu * G_s


        return dGFP
    G.set_behaviour(G_behaviour)
    plate.add_species(G)

    # add R to the plate
    U_R = np.ones(environment_size) * R_0
    R = Species("R", U_R)

    def R_behaviour(t, species, params):
        D_N, mu_max, K_mu, gamma, D_A, \
        alpha_T, beta_T, K_IT, n_IT, K_lacT, T7_0, \
        alpha_R, beta_R, K_IR, n_IR, K_lacR, R_0, \
        alpha_G, beta_G, n_A, K_A, n_R, K_R, X_0, G_s = params

        mu = dx(t, species) * receiver_flags
        #print('nir', n_IR)
        dR = (alpha_R * mu * (1 + (np.maximum(0, species['A']) / K_IR) ** n_IR)) / (
                1 + (np.maximum(0, species['A']) / K_IR) ** n_IR + K_lacR) + beta_R * mu - mu * np.maximum(0,
                                                                                                           species[
                                                                                                               'R'])
        return dR

    R.set_behaviour(R_behaviour)
    if bandpass:
        plate.add_species(R)

    return plate


def get_default_params():
    ## experimental parameters
    D_A = 1e-4  # / w ** 2  # mm^2 per min ***** IPTG DIFFUSION RATE
    T7_0 = 0  # ***** a.u. initial T7RNAP concentration per cell
    R_0 = 0  # ***** a.u. initial REPRESSOR concentration per cell
    GFP_0 = 0  # a.u. ***** initial GFP concentration per cell
    environment_size = (35, 35)
    X_0 = 0.3 * 10 / (environment_size[0] * environment_size[
        1])  # ***** initial cell count per grid position - rescaled to be in OD or 1e8 cells per grid pos
    ## growth parameters (currently Monod growth but can be replaced with fitted growth curves)
    D_N = 1e-4  # / w**2  # mm^2 per min  ***** nutrient diffusion rate
    mu_max = 0.02  # per min  *****  max growth rate
    K_mu = 1  # g  ***** growth Michaelis-Menten coeffecient
    gamma = 1E12  # cells per g  ***** yield
    gamma = 1E4  # OD or 1e8 cells per g  ***** yield rescaled

    ## From Zong paper
    alpha_T = 6223  #
    beta_T = 12.8  #
    K_IT = 1400  # 1.4e-6 M @ 1 molecule per nM
    K_IT = 1.4e-3  # mM
    n_IT = 2.3  #
    K_lacT = 15719  #
    alpha_R = 8025
    beta_R = 30.6
    K_IR = 1200  # 1.2e-6 M @ 1 molecule per nM
    K_IR = 1.2e-3  # mM
    n_IR = 2.2
    K_lacR = 14088
    alpha_G = 16462
    beta_G = 19
    n_A = 1.34
    K_A = 2532  # scaled
    n_R = 3.9
    K_R = 987
    G_s = 1

    params = [D_N, mu_max, K_mu, gamma, D_A,
              alpha_T, beta_T, K_IT, n_IT, K_lacT, T7_0,
              alpha_R, beta_R, K_IR, n_IR, K_lacR, R_0,
              alpha_G, beta_G, n_A, K_A, n_R, K_R, X_0, G_s]

    return params

def get_fitted_params(bandpass = False):
    if bandpass:
        gompertz_ps = [1.92683259e-01, 2.64236032e-04, 4.32035143e+02]  # bandpass second characterisation data
        X_0 = 2.376173539938517e-07  # from gompertz, bandpasss
    else:
        gompertz_ps = [2.11394439e-01, 2.41594404e-04, 4.53552100e+02]  # threshold second characterisation data
        X_0 = 3.1220959380630476e-06  # from gompertz, threshold
    params = get_default_params()

    # min: 24.799506417001446
    fitted_params = [1.77826648e-02,
                         1.64120920e+04,
                         2.47415565e-06,
                         2.92002839e-04,
                         6.96106975e-01,
                         1.32937555e+03,
                         7.86982891e-07,
                         7.57673598e+01,
                         3.24550002e+00,
                         7.55159303e+00,
                         5.31717871e+00,
                         1.84995110e-01] # threshold old model



    # min: 2.175147707185371
    BP_params = [2.85879101e+04,
                 6.09622809e-05,
                 4.09154708e-03,
                 2.00000000e+01,
                 8.84861563e+04,
                 1.03251547e+00,
                 1.06590408e+01,
                 8.19685211e-01] #old model


    # min: 26.930061095280045 with the updated model
    fitted_params = [2.09718170e-02,
                     4.49362919e+04,
                     2.34638872e-05,
                     4.45234986e-05,
                     7.11988626e-01,
                     3.35441602e+04,
                     3.55509735e-07,
                     8.58228897e+01,
                     2.89591988e+00,
                     1.25306724e+01,
                     1.56052788e+00,
                     1.23855350e-01]

    '''
    # min: 3.792371477640465 using threshold params and new model, these turn off really early
    BP_params = [7.15567501e+04,
                 1.33463125e-04,
                 9.15605330e-04,
                 1.05108079e+01,
                 4.53450373e+04,
                 5.09334794e-01,
                 2.00000000e+01,
                 3.54010551e+01]
    '''

    params[4:11] = fitted_params[0:7]
    params[17:21] = fitted_params[7:11]
    params[-1] = fitted_params[11]


    params[-14:-8] = BP_params[-8:-2]

    params[-4:-2] = BP_params[-2:]



    return params, gompertz_ps


