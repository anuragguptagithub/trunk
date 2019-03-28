from __future__ import unicode_literals

#import unittest
#import random
#from yade.wrapper import *
#from yade import utils

import unittest
import random,math
from yade.wrapper import *
from yade._customConverters import *
from yade import utils
from yade import *
from minieigen import *


class TestUtils(unittest.TestCase):
	def setUp(self):
		pass # no setup needed for tests here
	def testUserCreatedInteraction(self):
		O.bodies.append([utils.sphere((0,0,0),0.5),
			utils.sphere((2,0,0),0.5), #(0,1) no overlap , no contacts
			utils.sphere((0.9,0.9,0),0.5), #(0,2) overlapping bounds, no contacts
			utils.sphere((-0.99,0,0),0.5)]) #(0,3) overlaping + contact
		O.dt=0
		O.dynDt=False
		O.step()
		i=utils.createInteraction(0,1)
		self.assert_(i.iterBorn==1 and i.iterMadeReal==1)
		j=utils.createInteraction(0,2)
		self.assert_(j.iterBorn==1 and j.iterMadeReal==1)
		self.assertRaises(RuntimeError,lambda: utils.createInteraction(0,3))