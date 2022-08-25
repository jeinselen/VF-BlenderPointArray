bl_info = {
	"name": "VF Point Array",
	"author": "John Einselen - Vectorform LLC",
	"version": (0, 8),
	"blender": (2, 80, 0),
	"location": "Scene (edit mode) > VF Tools > Point Array",
	"description": "Creates point arrays with randomised scales and poisson disc sampling",
	"warning": "inexperienced developer, use at your own risk",
	"wiki_url": "",
	"tracker_url": "",
	"category": "3D View"}

# Based on the following resources:
# https://blender.stackexchange.com/questions/95616/generate-x-cubes-at-random-locations-but-not-inside-each-other
# https://blender.stackexchange.com/questions/1371/organic-yet-accurate-modeling-with-the-golden-spiral
# https://blender.stackexchange.com/questions/117558/how-to-add-vertices-into-specific-vertex-groups
# https://blender.stackexchange.com/questions/55484/when-to-use-bmesh-update-edit-mesh-and-when-mesh-update
# 
# If I ever want to do a hollow sphere shape, maybe start here: https://www.jasondavies.com/poisson-disc/

import bpy
from bpy.app.handlers import persistent
import bmesh
from random import uniform
from mathutils import Vector
import time

###########################################################################
# Main class

class VF_Point_Array(bpy.types.Operator):
	bl_idname = "vfpointarray.offset"
	bl_label = "Replace Mesh" # "Create Points" is a lot nicer, but I'm concerned this is a real easy kill switch for important geometry!
	bl_description = "Create points using the selected options, deleting and replacing the currently selected mesh"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		elements = bpy.context.scene.vf_point_array_settings.max_elements # target number of points
		failures = bpy.context.scene.vf_point_array_settings.max_failures # maximum number of consecutive failures
		attempts = bpy.context.scene.vf_point_array_settings.max_attempts # maximum number of iterations to try and meet the target number of points
		shapeX = bpy.context.scene.vf_point_array_settings.area_size[0]*0.5 # X distribution radius
		shapeY = bpy.context.scene.vf_point_array_settings.area_size[1]*0.5 # Y distribution radius
		shapeZ = bpy.context.scene.vf_point_array_settings.area_size[2]*0.5 # Z distribution radius
		minimumR = bpy.context.scene.vf_point_array_settings.scale_min*0.5 # minimum radius of the generated point
		maximumR = bpy.context.scene.vf_point_array_settings.scale_max*0.5 # maximum radius of the generated point
		# mediumR = min(minimumR * 2.0, minimumR + (maximumR - minimumR) * 0.5) # Auto calculate a threshold size to start using as the maximum after a certain number of failures have occurred (this would be nice as a setting, but for now I'm just testing it as a hard-coded variable)
		# failuresHalf = failures * 0.5 # Threshold for the mediumR override
		# Unfortunately it actually slows things down because it's constantly checking? I think? Yikes!
		within = True if bpy.context.scene.vf_point_array_settings.area_alignment == "RADIUS" else False # enable radius compensation to force all elements to fit within the shape boundary
		circular = True if bpy.context.scene.vf_point_array_settings.area_shape == "CYLINDER" else False # enable circular masking
		spherical = True if bpy.context.scene.vf_point_array_settings.area_shape == "SPHERE" else False # enable spherical masking

		# Get the currently active object
		obj = bpy.context.object

		# Create a radius weight map if it doesn't already exist
		# try:
		#     obj.vertex_groups["radius"]
		# except NameError:
		# 	group = obj.vertex_groups.new(name="radius")
		# else:
		# 	group = obj.vertex_groups["radius"]

		if len(obj.vertex_groups) > 0 and obj.vertex_groups["radius"]:
			group = obj.vertex_groups["radius"]
		else:
			group = obj.vertex_groups.new(name="radius")

		# Create a new bmesh
		bm = bmesh.new()

		# This does something important
		dl = bm.verts.layers.deform.verify()

		# Start timer
		timer = str(time.time())

		# Create points with poisson disc sampling
		points = []
		count = 0
		failmax = 0 # This is entirely for reporting purposes and is not needed structurally
		iteration = 0
		x = shapeX
		y = shapeY
		z = shapeZ

		# Loop until we're too tired to continue...
		while len(points) < elements and count < failures and iteration < attempts:
			iteration += 1
			count += 1

			# Create radius
			radius = uniform(minimumR, maximumR)

			# Set up edge limits (if enabled) and prevent divide-by-zero errors
			if within:
				x = max(0.0000001, shapeX-radius)
				y = max(0.0000001, shapeY-radius)
				z = max(0.0000001, shapeZ-radius)

			# Create point definition with radius
			point = [uniform(-x, x), uniform(-y, y), uniform(-z, z), radius]

			# Start check system (this prevents unnecessary cycles by exiting early if possible)
			check = 0

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

		# One last check, in case the stop cause was maximum count
		failmax = max(failmax, count) # This is entirely for reporting purposes and is not needed structurally

		# This creates vertices from the points list
		for p in points:
			v = bm.verts.new((p[0], p[1], p[2]))
			v[dl][group.index] = p[3]

		# print computing time
		# print( "VF Point Array - processing time: " + str(round(time.time() - float(timer), 2)) )
		# print( "VF Point Array - total attempts: " + str(iteration) )
		# print( "VF Point Array - maximum failure count: " + str(failmax) )
		# print( "VF Point Array - total points: " + str(count) )

		# Update the feedback strings
		context.scene.vf_point_array_settings.feedback_elements = str(len(points))
		context.scene.vf_point_array_settings.feedback_failures = str(failmax)
		context.scene.vf_point_array_settings.feedback_attempts = str(iteration)
		context.scene.vf_point_array_settings.feedback_time = str(round(time.time() - float(timer), 2))

		bm.to_mesh(obj.data)
		bm.free()
		obj.data.update() # This ensures the viewport updates!

		return {'FINISHED'}

###########################################################################
# User preferences and UI rendering class

class VFPointArrayPreferences(bpy.types.AddonPreferences):
	bl_idname = __name__

	show_feedback: bpy.props.BoolProperty(
		name="Show Processing Feedback",
		description='Displays relevant statistics from the last generated array',
		default=False)

	def draw(self, context):
		layout = self.layout
		layout.prop(self, "show_feedback")

###########################################################################
# Project settings and UI rendering classes

class vfPointArraySettings(bpy.types.PropertyGroup):
	area_shape: bpy.props.EnumProperty(
		name='Area Shape',
		description='Mask for the area where points will be created',
		items=[
			('BOX', 'Box', 'Cubic area, setting one of the dimensions to 0 will create a flat square or rectangle'),
			('CYLINDER', 'Cylinder', 'Cylindrical area, setting the Z dimension to 0 will create a flat circle or oval'),
			('SPHERE', 'Sphere', 'Spherical area, will be disabled if any of the dimensions are smaller than the maximum point size')
			],
		default='BOX')
	area_size: bpy.props.FloatVectorProperty(
		name="",
		subtype="XYZ",
		description="Size of the area where points will be created",
		default=[2.0, 2.0, 2.0],
		soft_min=0.0,
		soft_max=10.0,
		min=0.0,
		max=100.0)
	area_alignment: bpy.props.EnumProperty(
		name='Alignment',
		description='Sets how points align to the boundary of the array',
		items=[
			('CENTER', 'Center', 'Points will be contained within the area, but the radius will extend beyond the boundary'),
			('RADIUS', 'Radius', 'Fits the point radius within the boundary area (if the radius is larger than a dimension, it will still extend beyond)')
			],
		default='CENTER')

	scale_min: bpy.props.FloatProperty(
		name="Size Range",
		description="Minimum scale of the generated points (uses a weight map, which is unfortunately limited to 0.0-1.0 in Blender)",
		default=0.2,
		soft_min=0.1,
		soft_max=1.0,
		min=0.001,
		max=2.0,)
	scale_max: bpy.props.FloatProperty(
		name="Max",
		description="Maximum scale of the generated points (uses a weight map, which is unfortunately limited to 0.0-1.0 in Blender)",
		default=0.8,
		soft_min=0.1,
		soft_max=1.0,
		min=0.0001,
		max=2.0,)

	max_elements: bpy.props.IntProperty(
		name="Max Points",
		description="The maximum number of points that can be created (higher numbers will attempt to fill the space more)",
		default=100,
		soft_min=10,
		soft_max=1000,
		min=1,
		max=10000)
	max_failures: bpy.props.IntProperty(
		name="Max Failures",
		description="The maximum number of consecutive failures before quitting (higher numbers won't give up when the odds are poor)",
		default=1000,
		soft_min=100,
		soft_max=10000,
		min=10,
		max=100000)
	max_attempts: bpy.props.IntProperty(
		name="Max Attempts",
		description="The maximum number of placement attempts before quitting (higher numbers can take minutes to process)",
		default=10000,
		soft_min=1000,
		soft_max=100000,
		min=100,
		max=1000000)

	feedback_elements: bpy.props.StringProperty(
		name="Feedback",
		description="Stores the total points from the last created array",
		default="")
	feedback_failures: bpy.props.StringProperty(
		name="Feedback",
		description="Stores the maximum number of consecutive failures from the last created array",
		default="")
	feedback_attempts: bpy.props.StringProperty(
		name="Feedback",
		description="Stores the total attempts from the last created array",
		default="")
	feedback_time: bpy.props.StringProperty(
		name="Feedback",
		description="Stores the total time spent processing the last created array",
		default="")

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

			layout.prop(context.scene.vf_point_array_settings, 'area_shape')
			col=layout.column()
			col.prop(context.scene.vf_point_array_settings, 'area_size')
			layout.prop(context.scene.vf_point_array_settings, 'area_alignment')

			row = layout.row()
			row.prop(context.scene.vf_point_array_settings, 'scale_min')
			row.prop(context.scene.vf_point_array_settings, 'scale_max')

			layout.prop(context.scene.vf_point_array_settings, 'max_elements')
			layout.prop(context.scene.vf_point_array_settings, 'max_failures')
			layout.prop(context.scene.vf_point_array_settings, 'max_attempts')

			box = layout.box()
			if bpy.context.view_layer.objects.active.type == "MESH":
				layout.operator(VF_Point_Array.bl_idname)
				if len(context.scene.vf_point_array_settings.feedback_time) > 0 and bpy.context.preferences.addons['VF_pointArray'].preferences.show_feedback:
					boxcol=box.column()
					boxcol.label(text="Points created: " + context.scene.vf_point_array_settings.feedback_elements)
					boxcol.label(text="Successive fails: " + context.scene.vf_point_array_settings.feedback_failures) # Alternative: consecutive?
					boxcol.label(text="Total attempts: " + context.scene.vf_point_array_settings.feedback_attempts)
					boxcol.label(text="Processing Time: " + context.scene.vf_point_array_settings.feedback_time)
				box.label(text="WARNING: replaces mesh")
			else:
				box.label(text="Selected object must be a mesh")
		except Exception as exc:
			print(str(exc) + " | Error in VF Point Array panel")

classes = (VFPointArrayPreferences, VF_Point_Array, vfPointArraySettings, VFTOOLS_PT_point_array)

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
