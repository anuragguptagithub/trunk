# -*- coding: utf-8 -*-
#*************************************************************************
#  Copyright (C) 2010 by Bruno Chareyre                                  *
#  bruno.chareyre_at_grenoble-inp.fr                                     *
#                                                                        *
#  This program is free software; it is licensed under the terms of the  *
#  GNU General Public License v2 or later. See file LICENSE for details. *
#*************************************************************************/

## Example script for using the DEM-PFV coupling introduced with E. Catalano, as reported in:
## * [Chareyre2012a] Chareyre, B., Cortis, A., Catalano, E., Barthélemy, E. (2012), Pore-scale modeling of viscous flow and induced forces in dense sphere packings. Transport in Porous Media (92), pages 473-493. DOI 10.1007/s11242-011-9915-6
## http://dx.doi.org/10.1007/s11242-011-9915-6
## * [Catalano2014a] Catalano, E., Chareyre, B., Barthélémy, E. (2013), Pore-scale modeling of fluid-particles interaction and emerging poromechanical effects. International Journal for Numerical and Analytical Methods in Geomechanics. DOI 10.1002/nag.2198
## http://arxiv.org/pdf/1304.4895.pdf
## Also used in:
## * Tong et al.2012 (http://dx.doi.org/10.2516/ogst/2012032)
## * Sari et al 2011 (http://people.3sr-grenoble.fr/users/bchareyre/pubs/SariChareyreCatalanoPhilippeVincens_Particles2011.pdf)


## The DEM-PFV is applied here to 1D consolidation (oedometer test). The example includes the determination of oedometer modulus Ee and permeability K.
## The 1D consolidation is simulated as a coupled problem and the analytical solution corresponding to the abovementionned Ee and K is used for comparison.
## See triax-tutorial/script-session1.py for more detailed explanations of the packing generation procedure.

## ______________   First section, similar to triax-tutorial/script-session1.py  _________________
from __future__ import print_function
from __future__ import unicode_literals
from yade import pack

num_spheres=1000# number of spheres
young=1e6
compFricDegree = 3 # initial contact friction during the confining phase
finalFricDegree = 30 # contact friction during the deviatoric loading
mn,mx=Vector3(0,0,0),Vector3(1,1,1) # corners of the initial packing

O.materials.append(FrictMat(young=young,poisson=0.5,frictionAngle=radians(compFricDegree),density=2600,label='spheres'))
O.materials.append(FrictMat(young=young,poisson=0.5,frictionAngle=0,density=0,label='walls'))
walls=aabbWalls([mn,mx],thickness=0,material='walls')
wallIds=O.bodies.append(walls)

sp=pack.SpherePack()
sp.makeCloud(mn,mx,-1,0.3333,num_spheres,False, 0.95,seed=1) #"seed" make the "random" generation always the same
sp.toSimulation(material='spheres')

triax=TriaxialStressController(
	maxMultiplier=1.+2e4/young, # spheres growing factor (fast growth)
	finalMaxMultiplier=1.+2e3/young, # spheres growing factor (slow growth)
	thickness = 0,
	stressMask = 7,
	max_vel = 0.005,
	internalCompaction=True, # If true the confining pressure is generated by growing particles
)

newton=NewtonIntegrator(damping=0.2)

O.engines=[
	ForceResetter(),
	InsertionSortCollider([Bo1_Sphere_Aabb(),Bo1_Box_Aabb()]),
	InteractionLoop(
		[Ig2_Sphere_Sphere_ScGeom(),Ig2_Box_Sphere_ScGeom()],
		[Ip2_FrictMat_FrictMat_FrictPhys()],
		[Law2_ScGeom_FrictPhys_CundallStrack()],label="iloop"
	),
	FlowEngine(dead=1,label="flow"),#introduced as a dead engine for the moment, see 2nd section
	GlobalStiffnessTimeStepper(active=1,timeStepUpdateInterval=100,timestepSafetyCoefficient=0.8),
	triax,
	newton
]

triax.goal1=triax.goal2=triax.goal3=-10000

while 1:
  O.run(1000, True)
  unb=unbalancedForce()
  if unb<0.001 and abs(-10000-triax.meanStress)/10000<0.001:
    break

setContactFriction(radians(finalFricDegree))

## ______________   Oedometer section   _________________

#A. Check bulk modulus of the dry material from load/unload cycles
triax.stressMask=2
triax.goal1=triax.goal3=0

triax.internalCompaction=False
triax.wall_bottom_activated=False
#load
triax.goal2=-11000; O.run(2000,1)
#unload
triax.goal2=-10000; O.run(2000,1)
#load
triax.goal2=-11000; O.run(2000,1)
e22=triax.strain[1]
#unload
triax.goal2=-10000; O.run(2000,1)

e22=e22-triax.strain[1]
modulus = 1000./abs(e22)

#B. Activate flow engine and set boundary conditions in order to get permeability
flow.dead=0
flow.defTolerance=0.3
flow.meshUpdateInterval=200
flow.useSolver=3
flow.permeabilityFactor=1
flow.viscosity=10
flow.bndCondIsPressure=[0,0,1,1,0,0]
flow.bndCondValue=[0,0,1,0,0,0]
flow.boundaryUseMaxMin=[0,0,0,0,0,0]
O.dt=0.1e-3
O.dynDt=False

O.run(1,1)
Qin = flow.getBoundaryFlux(2)
Qout = flow.getBoundaryFlux(3)
permeability = abs(Qin)/1.e-4 #size is one, we compute K=V/∇H
print("Qin=",Qin," Qout=",Qout," permeability=",permeability)

#C. now the oedometer test, drained at the top, impermeable at the bottom plate
flow.bndCondIsPressure=[0,0,0,1,0,0]
flow.bndCondValue=[0,0,0,0,0,0]
flow.updateTriangulation=True #force remeshing to reflect new BC immediately
newton.damping=0

#we want the theoretical value from Terzaghi's solution
#keep in mind that we are not in an homogeneous material and the small strain
#assumption is not verified => we don't expect perfect match
#there can be also an overshoot of pressure in the very beginning due to dynamic effects
Cv=permeability*modulus/1e4
zeroTime=O.time
zeroe22 = - triax.strain[1]
dryFraction=0.05 #the top layer is affected by drainage on a certain depth, we account for it here
drye22 = 1000/modulus*dryFraction
wetHeight=1*(1-dryFraction)

def consolidation(Tv): #see your soil mechanics handbook...
	U=1
	for k in range(50):
		M=pi/2*(2*k+1)
		U=U-2/M**2*exp(-M**2*Tv)
	return U

triax.goal2=-11000



from yade import plot

## a function saving variables
def history():
  	plot.addData(e22=-triax.strain[1]-zeroe22,e22_theory=drye22+(1-dryFraction)*consolidation((O.time-zeroTime)*Cv/wetHeight**2)*1000./modulus,t=O.time,p=flow.getPorePressure((0.5,0.1,0.5)),s22=-triax.stress(3)[1]-10000)
  	#plot.addData(e22=-triax.strain[1],t=O.time,s22=-triax.stress(2)[1],p=flow.MeasurePorePressure((0.5,0.5,0.5)))

O.engines=O.engines+[PyRunner(iterPeriod=200,command='history()',label='recorder')]
##make nice animations:
#O.engines=O.engines+[PyRunner(iterPeriod=200,command='flow.saveVtk()')]

from yade import plot
plot.plots={'t':('e22','e22_theory',None,'s22','p')}
plot.plot()
O.saveTmp()
O.timingEnabled=1
from yade import timing
print("starting oedometer simulation")
O.run(200,1)
timing.stats()

print("\nPress ▶ (the start button) to see graph.\n")

## Make more steps to see the convergence to the stationnary solution
