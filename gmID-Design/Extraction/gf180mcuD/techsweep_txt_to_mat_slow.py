import pandas as pd
import numpy as np
from numpy.core.records import fromarrays
from scipy.io import savemat

choice = 1  #start from 0
devices = ['nfet_03v3', 'pfet_03v3','nfet_05v0', 'pfet_05v0']
#devices = ['pfet_05v0']

# widths used for characterization
w = np.array([5.0, 5.0, 5.0, 5.0])
nfing = np.array([1, 1, 1, 1])
Lmin = np.array([0.28, 0.28, 0.6, 0.5])

# read ngspice data
df_raw = pd.read_csv('./simulation/techsweep_'+devices[choice]+'_slow.txt', sep='\s+')
par_names = df_raw.columns.to_list()
fet_name = par_names[1].split('[')[0]

# remove unwanted columns and rename for readability
df = df_raw.drop(['frequency', 'frequency.1'], axis=1)
df = df.apply(pd.to_numeric)
df.columns = df.columns.str.replace(fet_name, '')
df.columns = df.columns.str.replace(fet_name[1:], '')
df.columns = df.columns.str.replace('[dc]', '')
df.columns = df.columns.str.replace('onoise..', 'n')
df.columns = df.columns.str.removeprefix('@')
df.columns = df.columns.str.removeprefix('[')
df.columns = df.columns.str.removesuffix(']')
df

# sweep variable vectors
l =   np.round(np.unique(df['l'])*1e6, 2)
vgs = np.unique(df['vg'])
vds = np.unique(df['vd'])
vsb = np.unique(-df['vb'])


# ngspice sweep order is l, vgs, vds, vsb
dims = [len(l), len(vgs), len(vds), len(vsb)]
id = np.reshape(df['id'].values, dims)
vt = np.reshape(df['vth'].values, dims)
vdsat = np.reshape(df['vdsat'].values, dims)
gm = np.reshape(df['gm'].values, dims)
gmb = np.reshape(df['gmbs'].values, dims)
gds = np.reshape(df['gds'].values, dims)
cgg = np.reshape(df['cgg'].values, dims) \
      + np.reshape(df['cgdo'].values, dims) + np.reshape(df['cgso'].values, dims)
cgb = -np.reshape(df['cgb'].values, dims)
cgd = -np.reshape(df['cgd'].values, dims) \
      + np.reshape(df['cgdo'].values, dims)
cgs = -np.reshape(df['cgs'].values, dims) \
      + np.reshape(df['cgso'].values, dims)
cdd = np.reshape(df['cdd'].values, dims) \
      + np.reshape(df['capbd'].values, dims) \
      + np.reshape(df['cgdo'].values, dims)
css = np.reshape(df['css'].values, dims) \
      + np.reshape(df['capbs'].values, dims) \
      + np.reshape(df['cgso'].values, dims)
sth = np.reshape(df['nid'].values, dims)**2
sfl = np.reshape(df['n1overf'].values, dims)**2


dic = {
  "INFO": "GlobalFoundries, 180nm MCU CMOS , BSIM4",
  "CORNER": "Slow-Slow High Temperature",
  "TEMP": 125.0,
  "VGS": vgs,
  "VDS": vds,
  "VSB": vsb,
  "L": l,
  "W": w[choice],
  "NFING": nfing[choice],
  "ID": id,
  "VT": vt,
  "VDSAT": vdsat,
  "GM": gm,
  "GMB": gmb,
  "GDS": gds,
  "CGG": cgg,
  "CGB": cgb,
  "CGD": cgd,
  "CGS": cgs,
  "CDD": cdd,
  "CSS": css,
  "STH": sth,
  "SFL": sfl
}
savemat('./simulation/'+devices[choice]+'_slow.mat', {devices[choice]: dic})
