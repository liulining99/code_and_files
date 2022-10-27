import numpy as np
import torch
import torch.nn as nn
import sys
import traci
import os
from sumolib import checkBinary
import random
from agent import Agent

if 'SUMO_HOME' in os.environ:
    tools=os.path.join(os.environ['SUMO_HOME'],'tools')
    sys.path.append(tools)
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

if_show_gui = True

if not if_show_gui:
    sumoBinary=checkBinary('sumo')
else:
    sumoBinary=checkBinary('sumo-gui')

action_space=[[0,0,0,0],[0,0,0,1],[0,0,1,0],[0,0,1,1],[0,1,0,0],[0,1,0,1],[0,1,1,0],[0,1,1,1],
              [1,0,0,0],[1,0,0,1],[1,0,1,0],[1,0,1,1],[1,1,0,0],[1,1,0,1],[1,1,1,0],[1,1,1,1]]
#相序定义：东西直行，东西左转，南北直行，南北左转（相位切换存在3s黄灯时间）
switch=['GGGrrGrrrrGGGrrGrrrr','GrrGGGrrrrGrrGGGrrrr','GrrrrGGGrrGrrrrGGGrr','GrrrrGrrGGGrrrrGrrGG']

#控制方案定义
def control_left(order):#order为4*1矩阵，例如[0,0,1,1]
    shunxu = switch.index(traci.trafficlight.getRedYellowGreenState('79'))
    if order[0]==0:
        a=switch[shunxu]
    elif order[0]==1 and shunxu<len(switch)-1:
        a=switch[shunxu+1]
    elif order[0] == 1 and shunxu == len(switch) - 1:
        a=switch[0]
    return a

def control_up(order):#order为4*1矩阵，例如[0,0,1,1]
    shunxu = switch.index(traci.trafficlight.getRedYellowGreenState('84'))
    if order[1] == 0:
        a = switch[shunxu]
    elif order[1] == 1 and shunxu < len(switch) - 1:
        a = switch[shunxu + 1]
    elif order[1] == 1 and shunxu == len(switch) - 1:
        a = switch[0]
    return a

def control_right(order):#order为4*1矩阵，例如[0,0,1,1]
    shunxu = switch.index(traci.trafficlight.getRedYellowGreenState('81'))
    if order[2] == 0:
        a = switch[shunxu]
    elif order[2] == 1 and shunxu < len(switch) - 1:
        a = switch[shunxu + 1]
    elif order[2] == 1 and shunxu == len(switch) - 1:
        a = switch[0]
    return a

def control_down(order):#order为4*1矩阵，例如[0,0,1,1]
    shunxu = switch.index(traci.trafficlight.getRedYellowGreenState('74'))
    if order[3] == 0:
        a = switch[shunxu]
    elif order[3] == 1 and shunxu < len(switch) - 1:
        a = switch[shunxu + 1]
    elif order[3] == 1 and shunxu == len(switch) - 1:
        a = switch[0]
    return a

#状态定义：车速在（0.3*路长-0.8*路长）时低于15km/h，定义为1
def state():
    alpha1 = 0.3
    alpha2 = 0.8
    ss=[]
    all_loc=[]
    loc=[]
    v=[]
    speed=[]
    length=[]
    LANE = ["-115_0", "-115_1", "-115_2", "-115_3"]
    s=[6,6,6,6]
    for lane in LANE:
        ss.append(traci.lane.getLastStepVehicleIDs(lane))
        length.append(traci.lane.getLength(lane))#要改这里的参数，此状态求解方式只适用于东西进口道
    for lane_car in ss:
        for car in lane_car:
            v.append(round(traci.vehicle.getSpeed(car),2))
        speed.append(v)
        v=[]
    for lane_car in ss:
        for car in lane_car:
            # loc.append(round(abs(traci.vehicle.getPosition(car)[0]+17.8),2))#求解location函数有问题
            loc.append(length[ss.index(lane_car)]-traci.vehicle.getLanePosition(car))
        all_loc.append(loc)
        loc=[]
    for x in range(len(speed)):
        if len(speed[x])!=0:
            for y in range(len(speed[x])):
                v_car=speed[x][y]
                loc_car=all_loc[x][y]
                if v_car <= 15/3.6 and alpha1*length[x]<=loc_car<=alpha2*length[x]:
                    s[x]=1
                    break
                else:
                    s[x]=0
        else:
            s[x]=0
    return s

#奖励定义：edge上车辆流出数
def reward():
    edgevehicle=list(traci.edge.getLastStepVehicleIDs('-115'))
    return edgevehicle

s=[0,0,0,0]
EPSILON_DECAY=10000
EPSILON_START=1.0
EPSILON_END=0.02
TARGET_UPDATE_FREQUENCY=5
n_episode=1000
n_time_step=1800
n_state=4
n_action=len(action_space)
agent=Agent(n_input=n_state,n_output=n_action)
lastIDs=[]
lastoutIDs=[]

REWARD_BUFFER=np.empty(shape=n_episode)

sumocfgfile=r"C:\Users\lln\Desktop\baoding_sumo_opti\sumo_volume_change\junction_vehicle_fail.sumocfg"
for episode_i in range(n_episode):
    traci.start([sumoBinary, "-c", sumocfgfile])
    episode_reward = 0
    for step_i in range(n_time_step):
        traci.simulationStep(step_i+1)
        simulation_time = traci.simulation.getTime()
        epsilon = np.interp(episode_i*n_time_step+step_i,[0,EPSILON_DECAY],[EPSILON_START,EPSILON_END])
        random_sample = random.random()
        if random_sample <= epsilon:
            a = np.random.randint(0, len(action_space))
        else:
             a = agent.online_net.act(s)
        action=action_space[a]
        traci.trafficlight.setRedYellowGreenState("79", str(control_left(action)))
        traci.trafficlight.setRedYellowGreenState("84", str(control_up(action)))
        traci.trafficlight.setRedYellowGreenState("81", str(control_right(action)))
        traci.trafficlight.setRedYellowGreenState("74", str(control_down(action)))
        rew=reward()
        for id in lastIDs:
            if id not in rew:
                lastoutIDs.append(id)
        r=len(lastIDs)
        lastIDs=rew
        s_ = state()
        agent.memo.add_memo(s, a, r, s_)
        s=s_
        episode_reward += r
        REWARD_BUFFER[episode_i] = episode_reward

        batch_s, batch_a, batch_r, batch_s_ = agent.memo.sample()

        # Compute targets
        target_q_values = agent.target_net(batch_s_)
        max_target_q_values = target_q_values.max(dim=1, keepdim=True)[0]
        targets = batch_r + agent.GAMMA * max_target_q_values

        # Compute q_values
        q_values = agent.online_net(batch_s)
        a_q_values = torch.gather(input=q_values, dim=1, index=batch_a)

        # Compute loss
        loss = nn.functional.smooth_l1_loss(targets, a_q_values)

        # Gradient descent
        agent.optimizer.zero_grad()
        loss.backward()
        agent.optimizer.step()

    if episode_i % TARGET_UPDATE_FREQUENCY == 0:
        agent.target_net.load_state_dict(agent.online_net.state_dict())
        # Show the training process
        print("Episode:", episode_i)
        print("Avg_reward", np.mean(REWARD_BUFFER[:episode_i]))
    traci.close()