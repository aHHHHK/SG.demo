
import matplotlib.pyplot as plt

class Pid():
    def __init__(self, kp, ki, kd):
        self.KP = kp
        self.KI = ki
        self.KD = kd

        self.now_val = 0
        self.now_err = 0
        self.last_err = 0
        self.last_last_err = 0
        self.change_val = 0

    def cmd_pid(self,now_v,exp_val):
        self.last_last_err = self.last_err
        self.exp_val = exp_val
        self.last_err = self.now_err
        self.now_err = self.exp_val - now_v
        self.change_val = self.KP * (self.now_err - self.last_err) + self.KI * \
                          self.now_err + self.KD * (self.now_err - 2 * self.last_err + self.last_last_err)

        # print(self.now_val)

        self.now_val += self.change_val

        # print(self.change_val)
        # print(self.now_val)

        return self.now_val

    # def next_pid(self,now_v):
    #     self.last_last_err = self.last_err
    #     self.exp_val = exp_val
    #     self.last_err = self.now_err
    #     self.now_err = self.exp_val - now_v
    #     self.change_val = self.KP * (self.now_err - self.last_err) + self.KI * \
    #                       self.now_err + self.KD * (self.now_err - 2 * self.last_err + self.last_last_err)
    #
    #     # print(self.now_val)
    #
    #     self.now_val += self.change_val
    #
    #     # print(self.change_val)
    #     # print(self.now_val)
    #
    #     return self.now_val

# # #
# pid_val = []
# pid_change = []
# my_Pid = Pid(0.1, 0.2, 0.5, 0.05)
# for i in range(0, 100):
#     pid_val.append(my_Pid.cmd_pid(my_Pid.now_val))
#     # pid_change.append(my_Pid.cmd_pid())
# plt.plot(pid_val)
# # # plt.plot(pid_change)
# plt.show()
