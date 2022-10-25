bl_info = {
	"name": "VF Point Array",
	"author": "John Einselen - Vectorform LLC",
	"version": (1, 4, 1),
	"blender": (2, 90, 0),
	"location": "Scene (edit mode) > VF Tools > Point Array",
	"description": "Creates point arrays in cubic array, golden angle, and poisson disc sampling patterns",
	"warning": "inexperienced developer, use at your own risk",
	"wiki_url": "",
	"tracker_url": "",
	"category": "3D View"}

# Based on the following resources:
# https://blender.stackexchange.com/questions/95616/generate-x-cubes-at-random-locations-but-not-inside-each-other
# https://blender.stackexchange.com/questions/1371/organic-yet-accurate-modeling-with-the-golden-spiral
# https://blender.stackexchange.com/questions/117558/how-to-add-vertices-into-specific-vertex-groups
# https://blender.stackexchange.com/questions/55484/when-to-use-bmesh-update-edit-mesh-and-when-mesh-update
# https://blenderartists.org/t/custom-vertex-attributes-data/1311915/3
# https://www.jasondavies.com/poisson-disc/
# https://blender.stackexchange.com/questions/27536/csv-import-pointcloud-into-blender
# https://blender.stackexchange.com/questions/244980/dynamic-enum-property-translation-problem
# https://blender.stackexchange.com/questions/31346/python-create-polyline-and-polyloop
# ...and pulling some nice improvements from the related AN7 Point Generator

import bpy
from bpy.app.handlers import persistent
import bmesh
from random import uniform
from mathutils import Vector
import math
import time
import re

###########################################################################
# Main classes

class VF_Point_Grid(bpy.types.Operator):
	bl_idname = "vfpointgrid.offset"
	bl_label = "Replace Mesh" # "Create Points" is a lot nicer, but I'm concerned this is a real easy kill switch for important geometry!
	bl_description = "Create a grid of points using the selected options, deleting and replacing the currently selected mesh"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		gridX = bpy.context.scene.vf_point_array_settings.grid_count[0] # X distribution radius
		gridY = bpy.context.scene.vf_point_array_settings.grid_count[1] # Y distribution radius
		gridZ = bpy.context.scene.vf_point_array_settings.grid_count[2] # Z distribution radius
		space = bpy.context.scene.vf_point_array_settings.grid_spacing*2.0 # Spacing of the grid elements
		rand_rot = bpy.context.scene.vf_point_array_settings.random_rotation

		# Get the currently active object
		obj = bpy.context.object

		# Create a new bmesh
		bm = bmesh.new()

		# Set up attribute layers
		# We don't need to check for an existing vertex layer because this is a fresh Bmesh
		pi = bm.verts.layers.float.new('index')
		ps = bm.verts.layers.float.new('scale')
		pr = bm.verts.layers.float_vector.new('rotation')

		# Advanced attribute layers
		relativeX = 0.0 if gridX == 1 else 1.0 / ((float(gridX) - 1) * space)
		relativeY = 0.0 if gridY == 1 else 1.0 / ((float(gridY) - 1) * space)
		relativeZ = 0.0 if gridZ == 1 else 1.0 / ((float(gridZ) - 1) * space)
		pu = bm.verts.layers.float_vector.new('position_relative')
		pd = bm.verts.layers.float.new('position_distance')

		# Index setup
		count = gridX * gridY * gridZ - 1.0
		i = 0.0

		# Create points
		for x in range(0, gridX):
			for y in range(0, gridY):
				for z in range(0, gridZ):
					pointX = (float(x) - gridX*0.5 + 0.5)*space
					pointY = (float(y) - gridY*0.5 + 0.5)*space
					if bpy.context.scene.vf_point_array_settings.grid_ground:
						pointZ = (float(z) + 0.5)*space
						positionRelative = Vector([pointX * relativeX * 2.0, pointY * relativeY * 2.0, pointZ * relativeZ])
					else:
						pointZ = (float(z) - gridZ*0.5 + 0.5)*space
						positionRelative = Vector([pointX * relativeX * 2.0, pointY * relativeY * 2.0, pointZ * relativeZ * 2.0])
					v = bm.verts.new((pointX, pointY, pointZ))
					v[pi] = 0.0 if i == 0.0 else i / count
					i += 1.0
					v[ps] = space*0.5
					v[pr] = Vector([0.0, 0.0, 0.0]) if not rand_rot else Vector([uniform(-math.pi, math.pi), uniform(-math.pi, math.pi), uniform(-math.pi, math.pi)])
					v[pu] = positionRelative
					v[pd] = positionRelative.length

		# Replace object with new mesh data
		bm.to_mesh(obj.data)
		bm.free()
		obj.data.update() # This ensures the viewport updates

		return {'FINISHED'}

class VF_Point_Golden(bpy.types.Operator):
	bl_idname = "vfpointgolden.offset"
	bl_label = "Replace Mesh" # "Create Points" is a lot nicer, but I'm concerned this is a real easy kill switch for important geometry!
	bl_description = "Create a flat array of points using the golden angle, deleting and replacing the currently selected mesh"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		count = bpy.context.scene.vf_point_array_settings.golden_count # X distribution radius
		space = bpy.context.scene.vf_point_array_settings.golden_spacing # Spacing of the grid elements
		rand_rot = bpy.context.scene.vf_point_array_settings.random_rotation

		# Get the currently active object
		obj = bpy.context.object

		# Create a new bmesh
		bm = bmesh.new()

		# Set up attribute layers
		pi = bm.verts.layers.float.new('index')
		ps = bm.verts.layers.float.new('scale')
		pr = bm.verts.layers.float_vector.new('rotation')

		if bpy.context.scene.vf_point_array_settings.golden_fill:
			v = bm.verts.new((space * 0.8660254037844386467637231707529361834714026269051903140279034897, 0.0, 0.0)) # Magic value: sin(60°)
			v[pi] = 0
			v[ps] = space
			v[pr] = Vector([0.0, 0.0, 0.0]) if not rand_rot else Vector([uniform(-math.pi, math.pi), uniform(-math.pi, math.pi), uniform(-math.pi, math.pi)])
			count -= 1

		for i in range(1, count+1): # The original code incorrectly set the starting vertex at 0...and while Fermat's Spiral can benefit from an extra point near the middle, the exact centre does not work
			#theta = i * math.radians(137.5)
			theta = i * 2.3999632297286533222315555066336138531249990110581150429351127507 # many thanks to WolframAlpha for numerical accuracy like this
			r = space * math.sqrt(i)
			v = bm.verts.new((math.cos(theta) * r, math.sin(theta) * r, 0.0))
			v[pi] = i / count if bpy.context.scene.vf_point_array_settings.golden_fill else (0.0 if i == 1 else (i - 1.0) / (count - 1.0))
			v[ps] = space
			v[pr] = Vector([0.0, 0.0, 0.0]) if not rand_rot else Vector([uniform(-math.pi, math.pi), uniform(-math.pi, math.pi), uniform(-math.pi, math.pi)])

		# Replace object with new mesh data
		bm.to_mesh(obj.data)
		bm.free()
		obj.data.update() # This ensures the viewport updates

		return {'FINISHED'}

class VF_Point_Pack(bpy.types.Operator):
	bl_idname = "vfpointpack.offset"
	bl_label = "Replace Mesh" # "Create Points" is a lot nicer, but I'm concerned this is a real easy kill switch for important geometry!
	bl_description = "Create points using the selected options, deleting and replacing the currently selected mesh"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		elements = bpy.context.scene.vf_point_array_settings.max_elements # target number of points
		failures = bpy.context.scene.vf_point_array_settings.max_failures # maximum number of consecutive failures
		attempts = bpy.context.scene.vf_point_array_settings.max_attempts # maximum number of iterations to try and meet the target number of points
		shapeX = bpy.context.scene.vf_point_array_settings.area_size[0] * 0.5 # X distribution radius
		shapeY = bpy.context.scene.vf_point_array_settings.area_size[1] * 0.5 # Y distribution radius
		shapeZ = bpy.context.scene.vf_point_array_settings.area_size[2] * 0.5 # Z distribution radius
		minimumR = bpy.context.scene.vf_point_array_settings.scale_min # minimum radius of the generated point
		maximumR = bpy.context.scene.vf_point_array_settings.scale_max # maximum radius of the generated point
		circular = True if bpy.context.scene.vf_point_array_settings.area_shape == "CYLINDER" else False # enable circular masking
		spherical = True if bpy.context.scene.vf_point_array_settings.area_shape == "SPHERE" else False # enable spherical masking
		hull = True if bpy.context.scene.vf_point_array_settings.area_shape == "HULL" else False # enable spherical masking
		trim = bpy.context.scene.vf_point_array_settings.area_truncate * 2.0 - 1.0 # trim hull extent
		within = True if bpy.context.scene.vf_point_array_settings.area_alignment == "RADIUS" else False # enable radius compensation to force all elements to fit within the shape boundary
		rand_rot = bpy.context.scene.vf_point_array_settings.random_rotation

		# Get the currently active object
		obj = bpy.context.object

		# Create a new bmesh
		bm = bmesh.new()

		# Set up attribute layers
		pi = bm.verts.layers.float.new('index')
		ps = bm.verts.layers.float.new('scale')
		pr = bm.verts.layers.float_vector.new('rotation')

		# Advanced attribute layers...designed for some pretty specific projects, but may be helpful in others
		relativeX = 0.0 if shapeX == 0.0 else 1.0 / shapeX
		relativeY = 0.0 if shapeY == 0.0 else 1.0 / shapeY
		relativeZ = 0.0 if shapeZ == 0.0 else 1.0 / shapeZ
		pu = bm.verts.layers.float_vector.new('position_relative')
		pd = bm.verts.layers.float.new('position_distance')

		# Start timer
		timer = str(time.time())

		# Create points with poisson disc sampling
		points = []
		count = 0
		failmax = 0 # This is entirely for reporting purposes and is not needed structurally
		iteration = 0

		# Loop until we're too tired to continue...
		while len(points) < elements and count < failures and iteration < attempts:
			iteration += 1
			count += 1
			# Create check system (this prevents unnecessary cycles by exiting early if possible)
			check = 0

			# Generate random radius
			radius = uniform(minimumR, maximumR)

			# Create volume
			x = shapeX
			y = shapeY
			z = shapeZ

			if hull:
				# Create normalised vector for the hull shape
				# This is a super easy way to generate random, albeit NOT evenly random, hulls...only works at full size, and begins to exhibit corner density when the trim value is above -1
				temp = Vector([uniform(-1.0, 1.0), uniform(-1.0, 1.0), uniform(trim, 1.0)]).normalized()
				# Check to see if the point is too far out of bounds
				if (temp[2] < trim):
					check = 1
				# Create point definition with radius
				point = [temp[0]*x, temp[1]*y, temp[2]*z, radius]
			else:
				# Set up edge limits (if enabled)
				if within:
					x -= radius
					y -= radius
					z -= radius
				# Prevent divide-by-zero errors
				x = max(x, 0.0000001)
				y = max(y, 0.0000001)
				z = max(z, 0.0000001)
				# Create point definition with radius
				point = [uniform(-x, x), uniform(-y, y), uniform(-z, z), radius]
				# Check if point is within circular or spherical bounds (if enabled)
				if spherical:
					check = int(Vector([point[0]/x, point[1]/y, point[2]/z]).length)
				elif circular:
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
				failmax = max(failmax, count) # This is entirely for reporting purposes and is not needed structurally
				# if count > failuresHalf: # This is a hard-coded efficiency attempt, dropping the maximum scale if we're getting a lot of failures
				# 	maximumR = mediumR
				count = 0

		# One last check, in case the stop cause was maximum failure count and this value wasn't updated in a successful check status
		failmax = max(failmax, count) # This is entirely for reporting purposes and is not needed structurally

		# Index setup
		count = len(points) - 1.0
		i = 0.0

		# This creates vertices from the points list
		for p in points:
			v = bm.verts.new((p[0], p[1], p[2]))
			v[pi] = 0.0 if i == 0.0 else i / count
			i += 1.0
			v[ps] = p[3]
			v[pr] = Vector([0.0, 0.0, 0.0]) if not rand_rot else Vector([uniform(-math.pi, math.pi), uniform(-math.pi, math.pi), uniform(-math.pi, math.pi)])
			positionRelative = Vector([p[0] * relativeX, p[1] * relativeY, p[2] * relativeZ])
			v[pu] = positionRelative
			v[pd] = positionRelative.length

		# Update the feedback strings
		context.scene.vf_point_array_settings.feedback_elements = str(len(points))
		context.scene.vf_point_array_settings.feedback_failures = str(failmax)
		context.scene.vf_point_array_settings.feedback_attempts = str(iteration)
		context.scene.vf_point_array_settings.feedback_time = str(round(time.time() - float(timer), 2))

		bm.to_mesh(obj.data)
		bm.free()
		obj.data.update() # This ensures the viewport updates

		return {'FINISHED'}

class VF_CSV_Line(bpy.types.Operator):
	bl_idname = "vfcsvline.create"
	bl_label = "Replace Mesh" # "Create Points" is a lot nicer, but I'm concerned this is a real easy kill switch for important geometry!
	bl_description = "Create a polyline of points using the selected options, deleting and replacing the currently selected mesh"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		# Load CSV data
		source = int(bpy.context.scene.vf_point_array_settings.csv_source)
		source = bpy.data.texts[source].as_string()
		source = re.sub(r'[^\n\,\d\.\-]', "", source) # Cleanse input data...sorta...horribly...
		data = [i.split(',') for i in source.split('\n')]

		# Remove first row if header should be skipped or if no numerical data exists in the first element
		if bpy.context.scene.vf_point_array_settings.skip_header or not data[0][0]:
			data.pop(0)

		# Return an error if the array contains less than two rows or one column
		if len(data) < 2 or len(data[1]) < 1:
			return {'ERROR'}

		# Load additional variables
		rand_rotation = bpy.context.scene.vf_point_array_settings.random_rotation
		rand_scale = bpy.context.scene.vf_point_array_settings.random_scale
		minimumR = bpy.context.scene.vf_point_array_settings.scale_min # minimum radius of the generated point
		maximumR = bpy.context.scene.vf_point_array_settings.scale_max # maximum radius of the generated point

		# Get the currently active object
		obj = bpy.context.object
		
		# Create a new bmesh
		bm = bmesh.new()
		
		# Set up attribute layers
		# We don't need to check for an existing vertex layer because this is a fresh Bmesh
		pi = bm.verts.layers.float.new('index')
		ps = bm.verts.layers.float.new('scale')
		pr = bm.verts.layers.float_vector.new('rotation')

		# Cycle through rows
		i = 0 # Track index
		count = len(data)
		for row in data:
			pointX = float(row[0]) if len(row) > 0 else 0.0
			pointY = float(row[1]) if len(row) > 1 else 0.0
			pointZ = float(row[2]) if len(row) > 2 else 0.0
			v = bm.verts.new((float(pointX), float(pointY), float(pointZ)))
			v[pi] = 0.0 if i == 0.0 else i / count
			i += 1 # Increment index
			v[ps] = 1.0 if not rand_scale else uniform(minimumR, maximumR)
			v[pr] = Vector([0.0, 0.0, 0.0]) if not rand_rotation else Vector([uniform(-math.pi, math.pi), uniform(-math.pi, math.pi), uniform(-math.pi, math.pi)])

		# Connect vertices
		if bpy.context.scene.vf_point_array_settings.connected_line:
			bm.verts.ensure_lookup_table()
			for j in range(i-1):
				bm.edges.new([bm.verts[j], bm.verts[j+1]])

		# Replace object with new mesh data
		bm.to_mesh(obj.data)
		bm.free()
		obj.data.update() # This ensures the viewport updates
		
		return {'FINISHED'}

###########################################################################
# User preferences and UI rendering class

class VFPointArrayPreferences(bpy.types.AddonPreferences):
	bl_idname = __name__

	show_feedback: bpy.props.BoolProperty(
		name="Show Processing Feedback",
		description='Displays relevant statistics from the last generated array',
		default=True)

	def draw(self, context):
		layout = self.layout
		layout.prop(self, "show_feedback")

###########################################################################
# Dynamic ENUM for text blocks

def textblocks_Enum(self,context):
	EnumItems = []
	for i,x in bpy.data.texts:
		EnumItems.append((i, x.name, x.lines[0].body))
	return EnumItems

###########################################################################
# Project settings and UI rendering classes

class vfPointArraySettings(bpy.types.PropertyGroup):
	array_type: bpy.props.EnumProperty(
		name='Array Type',
		description='The style of point array to create',
		items=[
			('GRID', 'Cubic Grid', 'Cubic array of points'),
			('GOLDEN', 'Golden Angle', 'Spherical area, will be disabled if any of the dimensions are smaller than the maximum point size'),
			('PACK', 'Poisson Disc', 'Generates random points while deleting any that overlap'),
			('CSV', 'CSV Data', 'Generates points using CSV data from the selected Blender text file (external .csv files require .py extension for Blender to open them)')
			],
		default='GRID')
	random_rotation: bpy.props.BoolProperty(
		name="Random Rotation",
		description="Rotate each generated point randomly",
		default=True,)

	# Cubic Grid settings
	grid_count: bpy.props.IntVectorProperty(
		name="Count",
		subtype="XYZ",
		description="Number of points created in each dimension",
		default=[8, 8, 8],
		step=10,
		soft_min=1,
		soft_max=32,
		min=1,
		max=1024,)
	grid_spacing: bpy.props.FloatProperty(
		name="Point Radius",
		description="Space between each point in the array",
		default=0.2,
		step=10,
		soft_min=0.0,
		soft_max=1.0,
		min=0.0,
		max=100.0,)
	grid_ground: bpy.props.BoolProperty(
		name="Grounded",
		description="Align the base of the cubic grid to Z = 0.0",
		default=False,)

	# Golden Angle settings
	# Often goes by Fibonacci or Vogel spiral, a specific type of Fermat spiral using the golden angle
	golden_count: bpy.props.IntProperty(
		name="Count",
		description="Number of points to create in the golden angle spiral",
		default=100,
		step=100,
		soft_min=10,
		soft_max=1000,
		min=1,
		max=100000,)
	golden_spacing: bpy.props.FloatProperty(
		name="Point Radius",
		description="Distance for each increment (this doesn't translate directly to spacing as the first two points will typically overlap)",
		default=0.2,
		step=10,
		soft_min=0.0,
		soft_max=1.0,
		min=0.0,
		max=100.0,)
	golden_fill: bpy.props.BoolProperty(
		name="Fill Gap",
		description="Starts the pattern with an extra point near the middle, better filling the visual gap that occurs in a true Vogel array",
		default=False,)

	# Poisson Disc settings
	area_shape: bpy.props.EnumProperty(
		name='Area Shape',
		description='Mask for the area where points will be created',
		items=[
			('BOX', 'Box', 'Cubic area, setting one of the dimensions to 0 will create a flat square or rectangle'),
			('CYLINDER', 'Cylinder', 'Cylindrical area, setting the Z dimension to 0 will create a flat circle or oval'),
			('SPHERE', 'Sphere', 'Spherical area, will be disabled if any of the dimensions are smaller than the maximum point size'),
			('HULL', 'Hull', 'Spherical hull, adding points just to the surface of a spherical area'),
			],
		default='BOX')
	area_size: bpy.props.FloatVectorProperty(
		name="Dimensions",
		subtype="XYZ",
		description="Size of the area where points will be created",
		default=[2.0, 2.0, 2.0],
		step=10,
		soft_min=0.0,
		soft_max=10.0,
		min=0.0,
		max=1000.0,)
	area_alignment: bpy.props.EnumProperty(
		name='Alignment',
		description='Sets how points align to the boundary of the array',
		items=[
			('CENTER', 'Center', 'Points will be contained within the area, but the radius will extend beyond the boundary'),
			('RADIUS', 'Radius', 'Fits the point radius within the boundary area (if the radius is larger than a dimension, it will still extend beyond)')
			],
		default='CENTER')
	area_truncate: bpy.props.FloatProperty(
		name="Truncate",
		description="Trims the extent of the hull starting at -Z",
		default=0.0,
		step=10,
		soft_min=0.0,
		soft_max=1.0,
		min=0.0,
		max=1.0,)

	# CSV data settings
	csv_source: bpy.props.EnumProperty(
		name = "Source",
		description = "Available text blocks (.csv files have to be named .py so Blender will recognise them as valid text resources)",
		items = textblocks_Enum)
	skip_header: bpy.props.BoolProperty(
		name="Skip Header",
		description="Remove the header row from CSV data",
		default=True,)
	connected_line: bpy.props.BoolProperty(
		name="Poly Line",
		description="Connect data points as polygon line",
		default=True,)
	random_scale: bpy.props.BoolProperty(
		name="Random Scale",
		description="Randomise scale between maximum and minimum",
		default=True,)

	# Global min/max scale settings
	scale_min: bpy.props.FloatProperty(
		name="Point Radius",
		description="Minimum scale of the generated points",
		default=0.2,
		step=10,
		soft_min=0.1,
		soft_max=1.0,
		min=0.0001,
		max=10.0,)
	scale_max: bpy.props.FloatProperty(
		name="Point Radius Maximum",
		description="Maximum scale of the generated points",
		default=0.8,
		step=10,
		soft_min=0.1,
		soft_max=1.0,
		min=0.0001,
		max=10.0,)

	# Maximum generation limits
	max_elements: bpy.props.IntProperty(
		name="Max Points",
		description="The maximum number of points that can be created (higher numbers will attempt to fill the space more)",
		default=100,
		step=10,
		soft_min=10,
		soft_max=1000,
		min=1,
		max=10000,)
	max_failures: bpy.props.IntProperty(
		name="Max Failures",
		description="The maximum number of consecutive failures before quitting (higher numbers won't give up when the odds are poor)",
		default=10000,
		step=100,
		soft_min=100,
		soft_max=100000,
		min=10,
		max=1000000,)
	max_attempts: bpy.props.IntProperty(
		name="Max Attempts",
		description="The maximum number of placement attempts before quitting (higher numbers can take minutes to process)",
		default=1000000,
		step=1000,
		soft_min=1000,
		soft_max=10000000,
		min=100,
		max=100000000,)

	# Persistent feedback data
	feedback_elements: bpy.props.StringProperty(
		name="Feedback",
		description="Stores the total points from the last created array",
		default="",)
	feedback_failures: bpy.props.StringProperty(
		name="Feedback",
		description="Stores the maximum number of consecutive failures from the last created array",
		default="",)
	feedback_attempts: bpy.props.StringProperty(
		name="Feedback",
		description="Stores the total attempts from the last created array",
		default="",)
	feedback_time: bpy.props.StringProperty(
		name="Feedback",
		description="Stores the total time spent processing the last created array",
		default="",)

class VFTOOLS_PT_point_array(bpy.types.Panel):
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_category = 'VF Tools'
	bl_order = 0
	bl_label = "Point Array"
	bl_idname = "VFTOOLS_PT_point_array"

	@classmethod
	def poll(cls, context):
		return True

	def draw_header(self, context):
		try:
			layout = self.layout
		except Exception as exc:
			print(str(exc) + " | Error in VF Point Array panel header")

	def draw(self, context):
		try:
			layout = self.layout
			layout.use_property_split = True
			layout.use_property_decorate = False # No animation

			layout.prop(context.scene.vf_point_array_settings, 'array_type')

			# Cubic Grid UI
			if bpy.context.scene.vf_point_array_settings.array_type == "GRID":
				col=layout.column()
				col.prop(context.scene.vf_point_array_settings, 'grid_count')
				layout.prop(context.scene.vf_point_array_settings, 'grid_spacing')
				layout.prop(context.scene.vf_point_array_settings, 'grid_ground')
				layout.prop(context.scene.vf_point_array_settings, 'random_rotation')
				box = layout.box()
				if bpy.context.view_layer.objects.active.type == "MESH" and bpy.context.object.mode == "OBJECT":
					layout.operator(VF_Point_Grid.bl_idname)
					box.label(text="Generate " + str(bpy.context.scene.vf_point_array_settings.grid_count[0] * bpy.context.scene.vf_point_array_settings.grid_count[1] * bpy.context.scene.vf_point_array_settings.grid_count[2]) + " points")
					box.label(text="WARNING: replaces mesh")

			# Golden Angle UI
			elif bpy.context.scene.vf_point_array_settings.array_type == "GOLDEN":
				layout.prop(context.scene.vf_point_array_settings, 'golden_count')
				layout.prop(context.scene.vf_point_array_settings, 'golden_spacing')
				layout.prop(context.scene.vf_point_array_settings, 'golden_fill')
				layout.prop(context.scene.vf_point_array_settings, 'random_rotation')
				box = layout.box()
				if bpy.context.view_layer.objects.active.type == "MESH" and bpy.context.object.mode == "OBJECT":
					layout.operator(VF_Point_Golden.bl_idname)
					box.label(text="WARNING: replaces mesh")

			# Poisson Disc UI
			elif bpy.context.scene.vf_point_array_settings.array_type == "PACK":
				layout.prop(context.scene.vf_point_array_settings, 'area_shape')
				col=layout.column()
				col.prop(context.scene.vf_point_array_settings, 'area_size')

				if bpy.context.scene.vf_point_array_settings.area_shape == "HULL":
					layout.prop(context.scene.vf_point_array_settings, 'area_truncate')
				else:
					layout.prop(context.scene.vf_point_array_settings, 'area_alignment')

				row = layout.row()
				row.prop(context.scene.vf_point_array_settings, 'scale_min')
				row.prop(context.scene.vf_point_array_settings, 'scale_max')

				layout.prop(context.scene.vf_point_array_settings, 'random_rotation')

				layout.prop(context.scene.vf_point_array_settings, 'max_elements')
				layout.prop(context.scene.vf_point_array_settings, 'max_failures')
				layout.prop(context.scene.vf_point_array_settings, 'max_attempts')

				box = layout.box()
				if bpy.context.view_layer.objects.active.type == "MESH" and bpy.context.object.mode == "OBJECT":
					layout.operator(VF_Point_Pack.bl_idname)
					if len(context.scene.vf_point_array_settings.feedback_time) > 0 and bpy.context.preferences.addons['VF_pointArray'].preferences.show_feedback:
						boxcol=box.column()
						boxcol.label(text="Points created: " + context.scene.vf_point_array_settings.feedback_elements)
						boxcol.label(text="Successive fails: " + context.scene.vf_point_array_settings.feedback_failures) # Alternative: consecutive?
						boxcol.label(text="Total attempts: " + context.scene.vf_point_array_settings.feedback_attempts)
						boxcol.label(text="Processing Time: " + context.scene.vf_point_array_settings.feedback_time)
					box.label(text="WARNING: replaces mesh")

			# CSV Data Import UI
			elif bpy.context.scene.vf_point_array_settings.array_type == "CSV":
				layout.prop(context.scene.vf_point_array_settings, 'csv_source')
				layout.prop(context.scene.vf_point_array_settings, 'skip_header')
				layout.prop(context.scene.vf_point_array_settings, 'connected_line')
				layout.prop(context.scene.vf_point_array_settings, 'random_rotation')
				layout.prop(context.scene.vf_point_array_settings, 'random_scale')
				if bpy.context.scene.vf_point_array_settings.random_scale:
					row = layout.row()
					row.prop(context.scene.vf_point_array_settings, 'scale_min')
					row.prop(context.scene.vf_point_array_settings, 'scale_max')

				box = layout.box()
				if bpy.context.view_layer.objects.active.type == "MESH" and bpy.context.object.mode == "OBJECT":
					layout.operator(VF_CSV_Line.bl_idname)
					box.label(text="WARNING: replaces mesh")

			# If the enum and this code is out of sync, we'll still create a box for feedback so the plugin doesn't crash
			else:
				box = layout.box()

			# Guidance feedback (coach the user on what will enable processing)
			if bpy.context.view_layer.objects.active.type != "MESH":
				box.label(text="Active item must be a mesh")
			elif bpy.context.object.mode != "OBJECT":
				box.label(text="Must be in object mode")

		except Exception as exc:
			print(str(exc) + " | Error in VF Point Array panel")

classes = (VFPointArrayPreferences, VF_Point_Grid, VF_Point_Golden, VF_Point_Pack, VF_CSV_Line, vfPointArraySettings, VFTOOLS_PT_point_array)

###########################################################################
# Addon registration functions

def register():
	for cls in classes:
		bpy.utils.register_class(cls)
	bpy.types.Scene.vf_point_array_settings = bpy.props.PointerProperty(type=vfPointArraySettings)

def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
	del bpy.types.Scene.vf_point_array_settings

if __name__ == "__main__":
	register()