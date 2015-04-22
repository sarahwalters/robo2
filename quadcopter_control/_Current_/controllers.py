#!/usr/bin/env python

"""
@author: claire

for spyder--># -*- coding: utf-8 -*-
for ROS----->#!/usr/bin/env python
"""
from model import QuadrotorParameters
from model import State
import numpy as np
import time
import rospy
from geometry_msgs.msg import Twist

class PidController:
    """ Creates a PID Controller that references the model/state information"""
    
    def __init__(self, Kd=4, Kp=3, Ki=5.5):
        """ Initalizes PID Controller object with PID constants """
        
        self.dt = 0.1 # timestep, ***static***
        self.proportional = np.zeros([3,1])
        self.integral = np.zeros([3,1])
        
        self.Kd = Kd
        self.Kp = Kp
        self.Ki = Ki


    def update(self, model):
        """ Performs PID update against setpoint [0,0,0], adjusts thetadot of 
        rotors, updates intregral states (no sensors)??"""
    
        # unpack quadrotor parameters
        g = model.quad.g
        m = model.quad.m
        k = model.quad.k
        
        #prevent intergral windup
        if max(self.integral) > 0.01:
            self.integral = np.zeros([3,1])

        # Compute total thrust. ***
        total = m * g / k / np.cos(self.proportional[0,0]) * np.cos(self.proportional[2,0])

        # Compute error against zero and adjust with PID 
        err = self.Kd * model.state.thetadots + self.Kp * self.proportional - self.Ki * self.integral

        # Update controller state.
        self.proportional = self.proportional + self.dt * model.state.thetadots
        self.integral = self.integral + self.dt * self.proportional

        return [err, total]

class RotorDynamicsModel():

    def __init__(self, state):
         """ make main model location, calls state and controller""" 
         self.state = state
         self.quad = QuadrotorParameters()


    def rotor_speeds(self, err, total):
        """ compute quadrotor rotor velocities with controller correction """
        
        # unpack error
        e1 = err[0,0]
        e2 = err[1,0]
        e3 = err[2,0]
 
        # unpack quadrotor parameters
        Ix = self.quad.I[0,0]
        Iy = self.quad.I[1,1]
        Iz = self.quad.I[2,2]
        k = self.quad.k
        L = self.quad.L
        b = self.quad.b

        # compute quadcopter rotor speed inputs
        rotor_speed = np.zeros([4,1])
        rotor_speed[0,0] = total/4 -(2 * b * e1 * Ix + e3 * Iz * k * L)/(4 * b * k * L)
        rotor_speed[1,0] = total/4 + e3 * Iz/(4 * b) - (e2 * Iy)/(2 * k * L)
        rotor_speed[2,0] = total/4 -(-2 * b * e1 * Ix + e3 * Iz * k * L)/(4 * b * k * L)
        rotor_speed[3,0] = total/4 + e3 * Iz/(4 * b) + (e2 * Iy)/(2 * k * L)

        return rotor_speed

class TranslationalController():

    def __init__(self, state):
         """ make main model location, calls state and controller""" 
         self.state = state
         self.quad = QuadrotorParameters()

    def torques(self, rotors):
        """Compute torques, given current inputs, length, drag coefficient, and thrust coefficient """
                
        tau = np.array([
        [self.quad.L * self.quad.k * (rotors[0,0] - rotors[2,0])],
        [self.quad.L * self.quad.k * (rotors[1,0] - rotors[3,0])],
        [self.quad.b * (rotors[0,0] - rotors[1,0] + rotors[2,0] - rotors[3,0])]
        ])

        return tau
        

    def angular_acceleration(self, rotors, omega):
        """ Compute angular acceleration in body frame """
        tau = self.torques(rotors)
        inv_I = np.linalg.inv(self.quad.I)
        
        cross = np.cross(omega.flatten(), np.dot(self.quad.I, omega).flatten())
        omegadot =  np.dot(inv_I, tau - np.reshape(cross,[3,1]))
        return omegadot


    def findW(self):
        """ ???? what is w ???
        ***math came from?*** """
      
        phi =   self.state.thetas[0,0]
        theta = self.state.thetas[1,0]
        psi =   self.state.thetas[2,0] #***not used ***??
    
        W = np.array([
            [1,      0,                 -1 * np.sin(theta)],
            [0,      np.cos(phi),       np.cos(theta)*np.sin(phi)],
            [0,      -1*np.sin(phi),    np.cos(theta)*np.cos(phi)]
            ])
        
        return W


    def thetadot2omega(self):
        """ convert derivatives of roll, pitch, yaw to omega
        ***what is omega***
        ***math came from?*** """
    
        W = self.findW()
        omega = np.dot(W,self.state.thetadots)
        
        return omega
        
        
    def omega2thetadot(self, omega):
        """ convert omega to derivatives of roll, pitch, yaw
        ***what is omega***
        ***math came from?*** """
    
        W = self.findW()
        inv_W = np.linalg.inv(W)
        self.state.thetadots = np.dot(inv_W, omega)


    def translate_model(self, rotors, dt):
         """ translates desired rotor speeds into new angular velocities"""
         omega = self.thetadot2omega()
         omegadot = self.angular_acceleration(rotors, omega)

         # Advance system state.
         omega = omega + dt * omegadot        
         self.omega2thetadot(omega)

class ROSTalker():
    """ """ 
    
    def __init__(self):
        """ """
        # initialize node and publisher
        self.pub = rospy.Publisher('/cmd_vel', Twist, queue_size=10)        
        rospy.init_node('talker', anonymous=True)

        #attributes
        self.subscriber_data = None
        self.rate = rospy.Rate(10) #10Hz
        self.twist = Twist() #sets velocity commands to 0
        
        # start subscriber
#       rospy.Subscriber('gazebo/model_states', ModelStates, self.callback)
        
        # initialize twist commands, note: inital statement is unpublished 
        self.pub.publish(self.twist)
	self.rate.sleep()
        

    def callback(self, msg):
	""" """
        self.subscriber_data = msg.pose[1]
        
    def rise(self,start_time): 
     	    
      	# start ascending
        self.twist.linear.z = 1
        self.pub.publish(self.twist)
        self.rate.sleep() 
        time.sleep(5) #rise time
        

        # stop rising
        rospy.loginfo('Start hovering')
        self.twist.linear.z = 0
        self.pub.publish(self.twist)
	self.rate.sleep() 

        
    def talk(self, ang_vel):
        self.twist = Twist()
        self.twist.angular.z = ang_vel[2,0]
        self.pub.publish(self.twist)  
	self.rate.sleep() 

