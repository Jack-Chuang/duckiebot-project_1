#!/usr/bin/env python3

import numpy as np
import rospy

from duckietown_msgs.msg import Twist2DStamped, Pose2DStamped

from duckietown.dtros import DTROS, NodeType, TopicType


class SensorFusionNode(DTROS):
    """
    Much of this code block is lifted from the official Duckietown Github:
    https://github.com/duckietown/dt-car-interface/blob/daffy/packages/dagu_car/src/velocity_to_pose_node.py

    The goal of this class is to use an Extended Kalman Filter to fuse estimates from a motion model with sensor readings from the cameras.
    We have left some code here from the official Duckietown repo, but you should feel free to discard it if you so choose. it or not

    The motion model callback as listed here will provide you with motion estimates, but you will
    need to linearize them in order to use the EKF. You will also need to figure out how to fuse in the data from the cameras.

    Args:
        node_name (:obj:`str`): a unique, descriptive name for the node that ROS will use

    Subscriber:
        ~velocity (:obj:`Twist2DStamped`): The robot velocity, typically obtained from forward kinematics

    Publisher:
        ~pose (:obj:`Pose2DStamped`): The integrated pose relative to the pose of the robot at node initialization

    """
    def __init__(self, node_name):
        # Initialize the DTROS parent class
        super(SensorFusionNode, self).__init__(
            node_name=node_name,
            node_type=NodeType.LOCALIZATION
        )

        # Get the vehicle name
        self.veh_name = rospy.get_namespace().strip("/")

        # Keep track of the last known pose
        self.last_pose = Pose2DStamped()
        self.last_theta_dot = 0
        self.last_v = 0

        # Setup the publisher
        self.pub_pose = rospy.Publisher(
            "~pose",
            Pose2DStamped,
            queue_size=1,
            dt_topic_type=TopicType.LOCALIZATION
        )

        # Setup the subscriber to the motion of the robot
        self.sub_velocity = rospy.Subscriber(
            f"/{self.veh_name}/kinematics_node/velocity",
            Twist2DStamped,
            self.motion_model_callback,
            queue_size=1
        )

        # ---
        self.log("Initialized.")

    def motion_model_callback(self, msg_velocity):
        """

        This function will use robot velocity information to give a new state
        Performs the calclulation from velocity to pose and publishes a messsage with the result.

        Args:
            msg_velocity (:obj:`Twist2DStamped`): the current velocity message

        """
        if self.last_pose.header.stamp.to_sec() > 0:  # skip first frame

            dt = (msg_velocity.header.stamp - self.last_pose.header.stamp).to_sec()

            # Integrate the relative movement between the last pose and the current
            theta_delta = self.last_theta_dot * dt
            # to ensure no division by zero for radius calculation:
            if np.abs(self.last_theta_dot) < 0.000001:
                # straight line
                x_delta = self.last_v * dt
                y_delta = 0
            else:
                # arc of circle
                radius = self.last_v / self.last_theta_dot
                x_delta = radius * np.sin(theta_delta)
                y_delta = radius * (1.0 - np.cos(theta_delta))

            # Add to the previous to get absolute pose relative to the starting position
            theta_res = self.last_pose.theta + theta_delta
            x_res = self.last_pose.x + x_delta * np.cos(self.last_pose.theta) - y_delta * np.sin(self.last_pose.theta)
            y_res = self.last_pose.y + y_delta * np.cos(self.last_pose.theta) + x_delta * np.sin(self.last_pose.theta)

            # Update the stored last pose
            self.last_pose.theta = theta_res
            self.last_pose.x = x_res
            self.last_pose.y = y_res

            # TODO Note how this puts the motion model estimate into a message and publishes the pose.
            # You will also need to publish the pose coming from sensor fusion when you correct
            # the estimates from the motion model
            msg_pose = Pose2DStamped()
            msg_pose.header = msg_velocity.header
            msg_pose.header.frame_id = self.veh_name
            msg_pose.theta = theta_res
            msg_pose.x = x_res
            msg_pose.y = y_res
            self.pub_pose.publish(msg_pose)

        self.last_pose.header.stamp = msg_velocity.header.stamp
        self.last_theta_dot = msg_velocity.omega
        self.last_v = msg_velocity.v


if __name__ == '__main__':
    # Initialize the node
    sensor_fusion_node = SensorFusionNode(node_name='sensor_fusion_node')
    # Keep it spinning to keep the node alive
    rospy.spin()
