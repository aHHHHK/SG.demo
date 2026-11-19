from pyomo.environ import *
from pyomo.dae import *

class SG():
  def __init__(self,t):
    self.t = t
    self.SGmodel = Block()
    self.SGmodel.lb = 1e-12

  def param_of_SG(self):
    self.SGmodel.g = Param(initialize=9.8)

    self.SGmodel.Vsd0 = Param(initialize=22)  # initialize=15)  #
    self.SGmodel.Vt = Param(initialize=169.80899283576434)  # --------------32.46
    self.SGmodel.Vr = Param(initialize=3.8255211610405406)  # --------------8.5
    self.SGmodel.Vdc = Param(initialize=5 * 2)  # -----------3.74

    self.SGmodel.mt = Param(initialize=206200)
    self.SGmodel.mr = Param(initialize=14382*2)
    self.SGmodel.md = Param(initialize=87666*2)

    self.SGmodel.Cp = Param(initialize=0.5)
    self.SGmodel.beida = Param(initialize=0.3)
    self.SGmodel.k = Param(initialize=25 / 7.7e3)
    self.SGmodel.Adc = Param(initialize=0.084)  # -------------0.696
    self.SGmodel.Ad = Param(initialize=11.1)  # ---------------可以算出来 约3.37！！！！！！！！！！！！！！
    self.SGmodel.Td = Param(initialize=6)

    # self.SGmodel.yipu = Param(initialize=0.964104756145436)

    self.SGmodel.F = Param(initialize=1e4)  # 传热面积 #实际100
    # self.SGmodel.KK = Param(initialize=3.2299598919242407)  # 传热系数 -----------------------估2.578
    self.SGmodel.aaa = Param(initialize=2e3)
    self.SGmodel.aa = Param(initialize=0.4)
    self.SGmodel.a = Param(initialize=1)  #
    # self.SGmodel.d_o = Param(initiali ze=19.1e-3) #传热管外径
    # self.SGmodel.d_i = Param(initialize=15.5e-3) #传热管内径
    # self.SGmodel.alpha_i = Param(initialize=4.22e7) #内侧传热系数 很大
    # self.SGmodel.S_r = Param(initialize=1.881) #上升管横截面 -----------------------估



  def var_of_SG(self):

    # self.SGmodel.a = Param(initialize=1.000)

    self.SGmodel.qf = Var(self.t, initialize=436, bounds=(self.SGmodel.lb, 560))
    self.SGmodel.qs = Var(self.t, initialize=436, bounds=(self.SGmodel.lb, 560))
    self.SGmodel.Q = Var(self.t, initialize= 726376, bounds=(1e3, 2e7))#53170*3e3
    self.SGmodel.Vwt = Var(self.t, initialize=51 ,bounds=(self.SGmodel.lb, 2e2))
    self.SGmodel.Vst = Var(self.t, initialize=50.9 ,bounds=(self.SGmodel.lb, 2e2))  # 0
    self.SGmodel.ar = Var(self.t, initialize=0.1, bounds=(self.SGmodel.lb, 1)) #蒸汽质量比例
    self.SGmodel.Vsd = Var(self.t, initialize=20, bounds=(5, 700))
    self.SGmodel.Vwd = Var(self.t, initialize=23.07400788, bounds=(self.SGmodel.lb, 700))  # 15.17076
    self.SGmodel.hc = Var(self.t, initialize=1666.9998713684217, bounds=(self.SGmodel.lb, 3e3))
    self.SGmodel.hf = Var(self.t, initialize=1031, bounds=(self.SGmodel.lb, 3e3))

    self.SGmodel.Level = Var(self.t, initialize=0, bounds=(self.SGmodel.lb, 80))
    self.SGmodel.P = Var(self.t, initialize=6.63,bounds=(0.1,15))

    self.SGmodel.ts = Var(self.t, initialize=263.94,bounds=(25,400))

    self.SGmodel.e11 = Var(self.t, initialize=761.758588032919)
    self.SGmodel.e12 = Var(self.t, initialize=-518.2728835193109)
    self.SGmodel.e21 = Var(self.t, initialize=822012.2135702729)
    self.SGmodel.e22 = Var(self.t, initialize=2421650.47099412)
    self.SGmodel.e32 = Var(self.t, initialize=1316255.0421739293)  # 1692044.583
    self.SGmodel.e33 = Var(self.t, initialize=11259206.291638665)  # 16610253.9439
    self.SGmodel.e42 = Var(self.t, initialize=352.65468925612714)  # 439.2246
    self.SGmodel.e43 = Var(self.t, initialize=-5432.516373060068)  # -4245.4468
    self.SGmodel.e44 = Var(self.t, initialize=23.333547437091436)

    self.SGmodel.hs = Var(self.t, initialize=2750.9598, bounds=(self.SGmodel.lb, None))
    self.SGmodel.hw = Var(self.t, initialize=1340.7, bounds=(self.SGmodel.lb, None))
    self.SGmodel.dens = Var(self.t, initialize=45.6085, bounds=(self.SGmodel.lb, None))
    self.SGmodel.denw = Var(self.t, initialize=713.629, bounds=(self.SGmodel.lb, None))
    self.SGmodel.dhs_dP = Var(self.t, initialize=-15.733)
    self.SGmodel.dhw_dP = Var(self.t, initialize=46.54)
    self.SGmodel.dens_dP = Var(self.t, initialize=6.292)
    self.SGmodel.denw_dP = Var(self.t, initialize=-17.0308)
    self.SGmodel.dts_dP = Var(self.t, initialize=8.3313)

    self.SGmodel.dav_dP = Var(self.t, initialize=-0.03364)  # -0.021
    self.SGmodel.dav_dar = Var(self.t, initialize=2.5347788)  # 5.044
    self.SGmodel.yita = Var(self.t, initialize=1.2640283)  # 0.38364
    self.SGmodel.av_ = Var(self.t, initialize=0.37767588, bounds=(self.SGmodel.lb, 1))  # 0.164
    self.SGmodel.qdc = Var(self.t, initialize=8.2e4/13)  ##660*300
    self.SGmodel.qr = Var(self.t, initialize=8.2e4/13)

    self.SGmodel.t_av = Var(self.t, initialize=580-273.15)  # 一次侧平均温度
    self.SGmodel.tff = Var(self.t, initialize=240)  # 一次侧平均温度

    self.SGmodel.G = Var(self.t, initialize=4.4156e+03)  # 质量流量
    # self.SGmodel.i_1 = Var(self.t, initialize=1470)  # 焓值
    # self.SGmodel.i_2 = Var(self.t, initialize=1307)  # 焓值
    # self.SGmodel.t_1 = Var(self.t, initialize=594)  # 1温度
    # self.SGmodel.t_2 = Var(self.t, initialize=565)  # 2温度
    # self.SGmodel.P_x = Var(self.t, initialize=10)  # 平均压强
    # self.SGmodel.P_1 = Var(self.t, initialize=11)  # 压强1
    # self.SGmodel.P_2 = Var(self.t, initialize=8)  # 压强2
    # self.SGmodel.x = Var(self.t, initialize=6.6)  # 体积流量


    self.SGmodel.e_P = Var(self.t, initialize=0)  # x
    self.SGmodel.dP = Var(self.t, initialize=0.01)  # x
    # self.SGmodel.dPP = Var(self.t, initialize=0.01)  # x
    # self.SGmodel.Vwd1 = Var(self.t, initialize=0.01)  # x
    # self.SGmodel.Vwd1 = Var(self.t, initialize=0.01)  # x
    # self.SGmodel.y = Var( initialize=1.01)  # x





    # self.SGmodel.mt = Var(initialize=89133.3 * 2, bounds=(1e4, 1e7))
    # self.SGmodel.mr = Var(initialize=385527.07150368404, bounds=(1e4, 1e7))
    # self.SGmodel.Ad = Var( initialize=10, bounds=(self.SGmodel.lb, 18))
    # self.SGmodel.Vsd0 = Var(initialize=22.31073577987275, bounds=(self.SGmodel.lb, 80))
    # self.SGmodel.Td = Var(initialize=6.99923232397427, bounds=(6, 12))
    # # # self.SGmodel.Vdc = Var(initialize=10, bounds=(1, 1e2))
    # self.SGmodel.Vt = Var(initialize=30, bounds=(1, 200))
    # # # self.SGmodel.F = Var(initialize=420*3e2 , bounds=(self.SGmodel.lb, 1e3))
    self.SGmodel.KK = Var(self.t,initialize=3.22 , bounds=(1, 6))
    # self.SGmodel.aaa = Var( initialize=1e3 , bounds=(1e3,1e4))
    # self.SGmodel.P_set = Var( initialize=0.3 )
    # self.SGmodel.aa = Var( initialize=0.46 , bounds=(0.31,0.47))

    #
    # self.SGmodel.kp_P = Var( initialize=1 , bounds=(1e-4,1e4))
    # self.SGmodel.ki_P = Var( initialize=0 , bounds=(0,100))
    # self.SGmodel.kd_P = Var( initialize=0 , bounds=(0,100))



    # # # self.SGmodel.hf_fix = Var(initialize=9e2 , bounds=(1, 1e3))
    # self.SGmodel.yipu = Var(initialize=0.9608152465690751)  # 传热效率


    # self.SGmodel.bb = Var(initialize=0.2, bounds=(1e-4, 0.7))  # 一次侧平均温度
    #
    #


  def dvar_of_SG(self):
    self.SGmodel.dVwt_dt = DerivativeVar(self.SGmodel.Vwt, initialize=3.30356e-07)
    self.SGmodel.dP_dt = DerivativeVar(self.SGmodel.P, initialize=2.8364367e-07)  # 1.288e-05
    self.SGmodel.dar_dt = DerivativeVar(self.SGmodel.ar, initialize=0.0002473)  # 4.024e-07
    self.SGmodel.dVsd_dt = DerivativeVar(self.SGmodel.Vsd, initialize=0.0390116)  # 5.114

    # self.SGmodel.de_P = DerivativeVar(self.SGmodel.e_P, initialize=0)  # 5.114
    # self.SGmodel.dde_P = DerivativeVar(self.SGmodel.de_P, initialize=0)  # 5.114

    # self.SGmodel.dqf_dt = DerivativeVar(self.SGmodel.qf, initialize=0)  # 5.114

    # self.SGmodel.song = Var(self.t, initialize=0, bounds=(-10, 10))  # 一次侧平均温度
  def fix0var_of_SG(self):
    pass

  def SG_model(self):

    # def ode_equ601(m, t):
    #   return m.t_av[t] == 300 +  m.kp_P * m.de_P[t] + m.ki_P * m.dde_P[t] + m.kd_P * m.e_P[t]
    #
    # self.SGmodel.ode601 = Constraint(self.t, rule=ode_equ601)
    #
    def ode_equ602(m, t):
      return m.KK[t] == -1.043e-06 * m.qs[t] ** 2 + 0.0024* m.qs[t]  + 2.291752423605748

    self.SGmodel.ode602 = Constraint(self.t, rule=ode_equ602)

    def ode_equ02(m, t):
      return m.e11[t] * m.dVwt_dt[t] + m.e12[t] * m.dP_dt[t] == (m.qf[t] - m.a*m.qs[t])

    self.SGmodel.ode2 = Constraint(self.t, rule=ode_equ02)

    def ode_equ03(m, t):  #
      return m.e21[t] * m.dVwt_dt[t] + m.e22[t] * m.dP_dt[t] == (m.Q[t] + m.qf[t] * m.hf[t] - m.a*m.qs[t] * m.hs[t])
  
    self.SGmodel.ode3 = Constraint(self.t, rule=ode_equ03)
  
    def ode_equ04(m, t):  #
      return m.e32[t] * m.dP_dt[t] + m.e33[t] * m.dar_dt[t] == (m.Q[t] - m.ar[t] * m.hc[t] * m.qr[t])
  
    self.SGmodel.ode4 = Constraint(self.t, rule=ode_equ04)
  
    def ode_equ05(m, t):
      return m.e42[t] * m.dP_dt[t] + m.e43[t] * m.dar_dt[t] + m.e44[t] * m.dVsd_dt[t] == (
               m.dens[t] / m.Td * (m.Vsd0 - m.Vsd[t]) + (m.hf[t] - m.hw[t]) / m.hc[t] * m.qf[t])
  
    self.SGmodel.ode5 = Constraint(self.t, rule=ode_equ05)
    #
    # def equ706(m, t):
    #   return (m.Level[t] * m.g * m.denw[t] + m.denw[t] * m.g * 10 == (m.Vwd[t] * m.denw[t] + m.Vsd[t] * m.dens[t]) * m.g / m.Ad +
    #           m.aaa * m.qr[t] **2 *(1/(m.av_[t] * m.dens[t] + (1-m.av_[t]) * m.denw[t]) + (m.Vsd[t] + m.Vwd[t])/(m.Vwd[t] * m.denw[t] + m.Vsd[t] * m.dens[t])) +
    #           m.g * (m.av_[t] * m.dens[t] + (1-m.av_[t]) * m.denw[t]) * 6  )
    #
    # self.SGmodel.equ706 = Constraint(self.t, rule=equ706)    #


    #
    def equ1706(m, t):
      return (m.dP[t] == (m.hf[t] - m.hw[t]) / m.hc[t] * m.qf[t]/m.dens[t])

    self.SGmodel.equ1706 = Constraint(self.t, rule=equ1706)

    def equ06(m, t):
      return m.hc[t] == m.hs[t] - m.hw[t]

    self.SGmodel.equ06 = Constraint(self.t, rule=equ06)

    def equ07(m, t):
      return m.e11[t] == m.denw[t] - m.dens[t]
  
    self.SGmodel.equ07 = Constraint(self.t, rule=equ07)
  
    def equ08(m, t):
      return m.e12[t] == 0
  
    self.SGmodel.equ08 = Constraint(self.t, rule=equ08)
  
    def equ09(m, t):
      return m.e21[t] == (m.denw[t] * m.hw[t] - m.dens[t] * m.hs[t])
  
    self.SGmodel.equ09 = Constraint(self.t, rule=equ09)
  
    def equ10(m, t):
      return m.e22[t] == (m.Vwt[t] * (m.hw[t] * m.denw_dP[t] + m.denw[t] * m.dhw_dP[t]) + m.Vst[t] * (
                m.hs[t] * m.dens_dP[t] + m.dens[t] * m.dhs_dP[t]) - m.Vt + m.mt * m.Cp * m.dts_dP[t])
  
    self.SGmodel.equ10 = Constraint(self.t, rule=equ10)
  
    def equ11(m, t):
      return m.e32[t] == ((m.denw[t] * m.dhw_dP[t] - m.ar[t] * m.hc[t] * m.denw_dP[t]) * (1 - m.av_[t]) * m.Vr + (
                (1 - m.ar[t]) * m.hc[t] * m.dens_dP[t] + m.dens[t] * m.dhs_dP[t]) * m.av_[t] * m.Vr + (
                                    m.dens[t] + (m.denw[t] - m.dens[t]) * m.ar[t]) * m.hc[t] * m.Vr * m.dav_dP[
                            t] - m.Vr + m.mr * m.Cp * m.dts_dP[t])
  
    self.SGmodel.equ11 = Constraint(self.t, rule=equ11)
  
    def equ12(m, t):
      return m.e33[t] == ((1 - m.ar[t]) * m.dens[t] + m.ar[t] * m.denw[t]) * m.hc[t] * m.Vr * m.dav_dar[t]
  
    self.SGmodel.equ12 = Constraint(self.t, rule=equ12)
  
    def equ13(m, t):  # 改动过
      return m.e42[t] * m.hc[t] == m.Vsd[t] * m.dens_dP[t] * m.hc[t] + (
                m.dens[t] * m.Vsd[t] * m.dhs_dP[t] + m.denw[t] * m.Vwd[t] * m.dhw_dP[t] - m.Vsd[t] - m.Vwd[
          t] + m.md * m.Cp * m.dts_dP[t]) + m.ar[t] * m.hc[t] * (1 + m.beida) * m.Vr * (
                       m.av_[t] * m.dens_dP[t] + (1 - m.av_[t]) * m.denw_dP[t] + (m.dens[t] - m.denw[t]) * m.dav_dP[t])
  
    self.SGmodel.equ13 = Constraint(self.t, rule=equ13)
  
    def equ14(m, t):
      return m.e43[t] == (m.ar[t] * ( m.beida) * (m.dens[t] - m.denw[t]) * m.Vr * m.dav_dar[t])
  
    self.SGmodel.equ14 = Constraint(self.t, rule=equ14)
  
    def equ15(m, t):
      return m.e44[t] == m.dens[t]
  
    self.SGmodel.equ15 = Constraint(self.t, rule=equ15)
  
    def equ16(m, t):
      return (m.dav_dP[t] * m.yita[t] * (1 + m.yita[t]) * m.dens[t] * (m.denw[t] - m.dens[t]) ** 2) == (
                (m.denw[t] * m.dens_dP[t] - m.dens[t] * m.denw_dP[t]) * (
                  m.yita[t] * (1 + m.yita[t]) * m.dens[t] + m.denw[t] * m.yita[t] - (1 + m.yita[t]) * (
                    m.dens[t] + m.denw[t]) * log(((1 + m.yita[t]) ** 2) ** 0.5)))
  
    self.SGmodel.equ16 = Constraint(self.t, rule=equ16)
  
    def equ17(m, t):
      return m.dav_dar[t] * (1 + m.yita[t]) * m.yita[t] * m.yita[t] * m.dens[t] == m.denw[t] * (
                (1 + m.yita[t]) * log(((1 + m.yita[t]) ** 2) ** 0.5) - m.yita[t])
  
    self.SGmodel.equ17 = Constraint(self.t, rule=equ17)
  
    def equ18(m, t):
      return m.yita[t] * m.dens[t] == m.ar[t] * (m.denw[t] - m.dens[t])
  
    self.SGmodel.equ18 = Constraint(self.t, rule=equ18)
  
    def equ19(m, t):
      return m.av_[t] * (m.denw[t] - m.dens[t]) * (m.denw[t] - m.dens[t]) * m.ar[t] == m.denw[t] * (
                (m.denw[t] - m.dens[t]) * m.ar[t] - m.dens[t] * (
                  log(((m.dens[t] + (m.denw[t] - m.dens[t]) * m.ar[t]) ** 2) ** 0.5) - log((m.dens[t] ** 2) ** 0.5)))
  
    self.SGmodel.equ19 = Constraint(self.t, rule=equ19)
  
    def equ20(m, t):
      return m.Vwd[t] == m.Vwt[t] - m.Vdc - (1 - m.av_[t]) * m.Vr
  
    self.SGmodel.equ20 = Constraint(self.t, rule=equ20)
  
    # def equ21(m, t):
    #   return (m.Level[t]) * m.Ad == (m.Vwd[t] + m.Vsd[t])
    #
    # self.SGmodel.equ21 = Constraint(self.t, rule=equ21)

    # def equ21(m, t):
    #   return m.Level[t] * m.Ad == m.Vwd[t] + m.Vsd[t] * m.aa #+ 2*m.dVsd_dt[t]
    #
    # self.SGmodel.equ21 = Constraint(self.t, rule=equ21)

    def equ706(m, t):
      return (m.Level[t] * m.g * m.denw[t]  == (m.Vwd[t] * m.denw[t] + m.Vsd[t] * m.dens[t]) * m.g / m.Ad +
              m.aaa * m.qr[t]  *( (m.Vsd[t] + m.Vwd[t])/(m.Vwd[t] * m.denw[t] + m.Vsd[t] * m.dens[t]))
              + m.g * (m.av_[t] * m.dens[t] + (1-m.av_[t]) * m.denw[t]) * 13   )

    self.SGmodel.equ706 = Constraint(self.t, rule=equ706)

    def equ22(m, t):
      return m.qr[t] ** 2 * m.k == 2 * m.denw[t] * m.Adc * (m.denw[t] - m.dens[t]) * m.g * m.av_[t] * m.Vr

    self.SGmodel.equ22 = Constraint(self.t, rule=equ22)
  
    def equ23(m, t):
      return m.Vt == m.Vst[t] + m.Vwt[t]
  
    self.SGmodel.equ23 = Constraint(self.t, rule=equ23)

    def equ24(m, t):
      return (m.qr[t] - m.qdc[t]) == -m.Vr * (
                m.av_[t] * m.dens_dP[t] + (1 - m.av_[t]) * m.denw_dP[t] + (m.dens[t] - m.denw[t]) * m.dav_dP[t]) * \
             m.dP_dt[t] + (m.denw[t] - m.dens[t]) * m.Vr * m.dav_dar[t] * m.dar_dt[t]

    self.SGmodel.equ24 = Constraint(self.t, rule=equ24)


    def equ104(m, t):
      return m.ts[t] == -0.003896*m.P[t]**4+0.1646*m.P[t]**3 -2.86*m.P[t]**2+30.81*m.P[t]+436.4 - 273.15

    self.SGmodel.equ104 = Constraint(self.t, rule=equ104)

    def equ105(m, t):
      return m.dts_dP[t] == -0.003896 * 4 * m.P[t] ** 3 + 0.1646 * 3 * m.P[t] ** 2 - 2.86 * 2 * m.P[t] + 30.81

    self.SGmodel.equ105 = Constraint(self.t, rule=equ105)

    def equ106(m, t):
      return m.denw[t] == 0.003841 * m.P[t] ** 4 - 0.1682 * m.P[t] ** 3 + 2.78 * m.P[t] ** 2 - 37.27 * m.P[t] + 912.8

    self.SGmodel.equ106 = Constraint(self.t, rule=equ106)

    def equ107(m, t):
      return m.dens[t] == 0.007774 * m.P[t] ** 3 - 0.02408 * m.P[t] ** 2 + 5.015 * m.P[t] - 0.07424

    self.SGmodel.equ107 = Constraint(self.t, rule=equ107)

    def equ108(m, t):
      return m.hw[t] == -0.01668 * m.P[t] ** 4 + 0.7115 * m.P[t] ** 3 - 12.13 * m.P[t] ** 2 + 139.4 * m.P[t] + 682.3

    self.SGmodel.equ108 = Constraint(self.t, rule=equ108)

    def equ109(m, t):
      return m.hs[t] == -0.007728 * m.P[t] ** 4 + 0.2819 * m.P[t] ** 3 - 4.621 * m.P[t] ** 2 + 20.73 * m.P[t] + 2776

    self.SGmodel.equ109 = Constraint(self.t, rule=equ109)

    def equ110(m, t):
      return m.denw_dP[t] == 0.003841 * 4 * m.P[t] ** 3 - 0.1682 * 3 * m.P[t] ** 2 + 2.78 * 2 * m.P[t] - 37.27

    self.SGmodel.equ110 = Constraint(self.t, rule=equ110)

    def equ111(m, t):
      return m.dens_dP[t] == 0.007774 * 3 * m.P[t] ** 2 - 0.02408 * 2 * m.P[t] + 5.015

    self.SGmodel.equ111 = Constraint(self.t, rule=equ111)

    def equ112(m, t):
      return m.dhw_dP[t] == -0.01668 * 4 * m.P[t] ** 3 + 0.7115 * 3 * m.P[t] ** 2 - 12.13 * 2 * m.P[t] + 139.4

    self.SGmodel.equ112 = Constraint(self.t, rule=equ112)

    def equ113(m, t):
      return m.dhs_dP[t] == -0.007728 * 4 * m.P[t] ** 3 + 0.2819 * 3 * m.P[t] ** 2 - 4.621 * 2 * m.P[t] + 20.73

    self.SGmodel.equ113 = Constraint(self.t, rule=equ113)




    def equ1114(m, t):
      return m.Q[t] == m.KK[t]  *m.F*(m.t_av[t] - m.ts[t]) #282 * (m.x * m.t_av[t])

    self.SGmodel.equ1114 = Constraint(self.t, rule=equ1114)
    #
    #
    #


    def equ1194(m, t):
      return m.hf[t] == (0.00186 * m.tff[t] ** 2 + 3.72 * m.tff[t] + 35.68)

    self.SGmodel.equ1194 = Constraint(self.t, rule=equ1194)


    #
    # def equ1115(m, t):
    #   return m.Q[t] == m.G[t] * (m.i_1[t] - m.i_2[t]) * m.yipu
    #
    # self.SGmodel.equ1115 = Constraint(self.t, rule=equ1115)
    # #
    #
    # def equ1116(m, t):
    #   return m.t_av[t] == (m.t_1[t] + m.t_2[t])/2
    #
    # self.SGmodel.equ1116 = Constraint(self.t, rule=equ1116)
    # #
    #
    # def equ1117(m, t):
    #   return m.P_x[t] == (m.P_1[t]+m.P_2[t])/2
    #
    # self.SGmodel.equ1117 = Constraint(self.t, rule=equ1117)
    # #
    # def equ1117(m, t):
    #   return m.P_x[t] == 0.0007039*m.t_av[t]**2 - 0.6845*m.t_av[t] + 169.6
    #
    # self.SGmodel.equ1117 = Constraint(self.t, rule=equ1117)
    # # #


    # def equ2117(m, t):
    #   return m.P_1[t] == 0.0007039*m.t_1[t]**2 - 0.6845*m.t_1[t] + 169.6
    #
    # self.SGmodel.equ2117 = Constraint(self.t, rule=equ2117)
    # #
    # def equ3117(m, t):
    #   return m.P_2[t] == 0.0007039*m.t_2[t]**2 - 0.6845*m.t_2[t] + 169.6
    #
    # self.SGmodel.equ3117 = Constraint(self.t, rule=equ3117)
    # #
    #
    # def equ1118(m, t):
    #   return m.G[t] == m.x[t] * (0.003841 * m.P_x[t] ** 4 - 0.1682 * m.P_x[t] ** 3 + 2.78 * m.P_x[t] ** 2 - 37.27 * m.P_x[t] + 912.8)
    #
    # self.SGmodel.equ1118 = Constraint(self.t, rule=equ1118)
    # #
    #
    # def equ1119(m, t):
    #   return m.i_1[t] == -0.01668 * m.P_1[t] ** 4 + 0.7115 * m.P_1[t] ** 3 - 12.13 * m.P_1[t] ** 2 + 139.4 * m.P_1[t] + 682.3
    #
    # self.SGmodel.equ1119 = Constraint(self.t, rule=equ1119)
    # #
    #
    # def equ1120(m, t):
    #   return m.i_2[t] == -0.01668 * m.P_2[t] ** 4 + 0.7115 * m.P_2[t] ** 3 - 12.13 * m.P_2[t] ** 2 + 139.4 * m.P_2[t] + 682.3
    #
    # self.SGmodel.equ1120 = Constraint(self.t, rule=equ1120)
    #




    # def equ115(m, t):
    #   return 1/m.K[t] == (m.d_o/m.d_i)*(1/m.alpha_i) + 1/m.alpha_o[t] + 0.26e-4 + 1.23e-4
    #
    # self.SGmodel.equ115 = Constraint(self.t, rule=equ115)
    #
    # def equ116(m, t):
    #   return m.alpha_o[t] == 0.557 * (m.P[t]**0.15) * (m.Q_r[t]**0.7)
    #
    # self.SGmodel.equ116 = Constraint(self.t, rule=equ116)
    #
    # def equ117(m, t):
    #   return m.Q_r[t] == m.qr[t] * (m.hw[t]*(1-m.ar[t]) + m.hs[t]*m.ar[t]) / m.S_r
    #
    # self.SGmodel.equ117 = Constraint(self.t, rule=equ117)



