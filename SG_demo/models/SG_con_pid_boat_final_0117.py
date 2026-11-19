from pyomo.core.base import *
from pyomo.environ import *
from pyomo.dae import *
class con_model():
    def __init__(self, m):
        from SG_for_SGqinshan_boat_a_0117 import SG

        global SG1
        SG1 = SG(m.t)
        m.add_component('SG1', SG1.SGmodel)
        SG1.param_of_SG()
        SG1.var_of_SG()
        SG1.dvar_of_SG()
        #SG1.fix0var_of_SG()
        SG1.SG_model()
