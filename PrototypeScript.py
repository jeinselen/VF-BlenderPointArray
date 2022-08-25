import bpy
import bmesh
from random import random
from random import uniform
from mathutils import Vector

import time

elements = 256 # target number of points
failures = 2560 # maximum number of consecutive failures
attempts = 25600 # maximum number of iterations to try and meet the target number of points
shapeX = 2.0 # X distribution radius
shapeY = 2.0 # Y distribution radius
shapeZ = 2.0 # Z distribution radius
minimumR = 0.1 # minimum scale
maximumR = 1.0 # maximum scale
within = True # enable radius compensation to force all elements to fit within the shape boundary
circular = True # enable circular masking
spherical = True # enable spherical masking

# Get the currently active object
obj = bpy.context.object

# Create a radius weight map if it doesn't already exist
if bpy.context.object.vertex_groups["radius"]:
    group = bpy.context.object.vertex_groups["radius"]
else:
    group = bpy.context.object.vertex_groups.new(name="radius")

# Create a new bmesh
bm = bmesh.new()

# This does something important
dl = bm.verts.layers.deform.verify()

# Start timer
timer = str(time.time())

# Create points with poisson disc sampling
points = []
count = 0
iteration = 0
x = shapeX
y = shapeY
z = shapeZ
# Prevent divide-by-zero errors later...just disable spherical or circular now
if z == 0.0 or within and z-maximumR <= 0.0:
    spherical = False
elif y == 0.0 or within and y-maximumR <= 0.0:
    spherical = False
    circular = False
elif x == 0.0 or within and x-maximumR <= 0.0:
    spherical = False
    circular = False

# Loop until we're too tired to continue...
while len(points) < elements and count < failures and iteration < attempts:
    iteration += 1
    count += 1

    # Create radius
    radius = uniform(minimumR, maximumR)

    # Set up edge limits (if enabled)
    if within:
        x = max(0.0, shapeX-radius)
        y = max(0.0, shapeY-radius)
        z = max(0.0, shapeZ-radius)

    # Create point definition with radius
    point = [uniform(-x, x), uniform(-y, y), uniform(-z, z), radius]

    # Start check system (this prevens unnecessary cycles by exiting early if possible)
    check = 0

    # Check if point is within circular or spherical bounds (if enabled)
    if spherical: # # and x > 0.0 and y > 0.0:
        check = int(Vector([point[0]/x, point[1]/y, point[2]/z]).length)
    elif circular: # and x > 0.0 and y > 0.0 and z > 0.0:
        check = int(Vector([point[0]/x, point[1]/y, 0.0]).length)

    # Check if it overlaps with other radii
    i = 0
    while i < len(points) and check == 0:
        if Vector([points[i][0]-point[0], points[i][1]-point[1], points[i][2]-point[2]]).length < (points[i][3] + point[3]):
            check = 1
        i += 1

    # If no collisions are detected, add the point to the list and reset the failure counter
    if check == 0:
        points.append(point)
        count = 0

# This creates vertices from the points list
for p in points:
    v = bm.verts.new((p[0], p[1], p[2]))
    v[dl][group.index] = p[3]

# print computing time
print( "VF Point Array - processing time: " + str(round(time.time() - float(timer), 2)) )
print( "VF Point Array - total attempts: " + str(iteration) )
print( "VF Point Array - last failure count: " + str(count) )

bm.to_mesh(obj.data)
bm.free()