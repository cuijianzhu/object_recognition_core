#!/usr/bin/env python

import sys
import argparse
import time
import tempfile
import os
import math
import subprocess

import couchdb

import ecto
from ecto_opencv import calib, highgui
import object_recognition
from object_recognition import dbtools, models, capture, observations
from ecto_object_recognition import reconstruction


def parse_args():
    parser = argparse.ArgumentParser(description='Computes a surface mesh of an object in the database')
    parser.add_argument('-s', '--session_id', metavar='SESSION_ID', dest='session_id', type=str, default='',
                       help='The session id to reconstruct.')
    parser.add_argument('--all', dest='compute_all', action='store_const',
                        const=True, default=False,
                        help='Compute meshes for all possible sessions.')
    parser.add_argument('--visualize', dest='visualize', action='store_const',
                        const=True, default=False,
                        help='Turn on visiualization')
    object_recognition.dbtools.add_db_options(parser)
    args = parser.parse_args()
    if args.compute_all == False and args.session_id == '':
        parser.print_help()
        sys.exit(1)
    return args

def mesh_session(session, args):
    db_reader = capture.ObservationReader('db_reader', session_id=session.id)
    depthTo3d = calib.DepthTo3d()
    rescale_depth = capture.RescaledRegisteredDepth() #this is for SXGA mode scale handling.
    surfel_reconstruction = reconstruction.SurfelReconstruction(corrDistForUpdate=0.02,
                                                                maxInterpolationDist=0.04,
                                                                starvationConfidence=2,
                                                                timeDiffForRemoval=25,
                                                                maxNormalAngle=90 * math.pi / 180)
    if True:
        plasm = ecto.Plasm()
        plasm.connect(
                      db_reader['K'] >> depthTo3d['K'],
                      db_reader['image'] >> rescale_depth['image'],
                      db_reader['depth'] >> rescale_depth['depth'],
                      rescale_depth[:] >> depthTo3d['depth'],
                      depthTo3d['points3d'] >> surfel_reconstruction['points3d'],
                      db_reader['K', 'R', 'T', 'image', 'mask'] >> surfel_reconstruction['K', 'R', 'T', 'image', 'mask'],
                      )
        if args.visualize:
            plasm.connect(
                      db_reader['image'] >> highgui.imshow('image', name='image')[:],
                      db_reader['depth'] >> highgui.imshow('depth', name='depth')[:],
                      db_reader['mask'] >> highgui.imshow('mask', name='mask')[:],
                      )
        ecto.view_plasm(plasm)
        sched = ecto.schedulers.Singlethreaded(plasm)
        sched.execute()

    if True:
        location = '/tmp/object_recognition/'
        mesh_script_txt = '''<!DOCTYPE FilterScript>
<FilterScript>
 <filter name="Surface Reconstruction: Poisson">
  <Param type="RichInt" value="8" name="OctDepth"/>
  <Param type="RichInt" value="8" name="SolverDivide"/>
  <Param type="RichFloat" value="2" name="SamplesPerNode"/>
  <Param type="RichFloat" value="1" name="Offset"/>
 </filter>
</FilterScript>     
        '''
        mesh_file_name = os.path.join(location, 'meshing.mlx')
        with open(mesh_file_name, 'w') as mesh_script:
            mesh_script.write(mesh_script_txt)
        try:
            os.makedirs(location)
        except Exception, e:
            pass
        name_base = str(session.id)
        surfel_ply = os.path.join(location, name_base + '.ply')
        print "Saving to :", surfel_ply
        surfel_saver = reconstruction.SurfelToPly(filename=surfel_ply)
        surfel_saver.inputs.at('model').copy_value(surfel_reconstruction.outputs.at('model'))
        surfel_saver.inputs.at('params').copy_value(surfel_reconstruction.outputs.at('params'))
        surfel_saver.inputs.at('camera_params').copy_value(surfel_reconstruction.outputs.at('camera_params'))

        surfel_saver.configure()
        surfel_saver.process() #manually thunk the cell's process function

#        mesh_args = ["meshlabserver", "-i", surfel_ply, "-o", meshed_ply, "-s", mesh_file_name, "-om", "vn", "fn", "vc", "fc"]
#        p = subprocess.Popen(mesh_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#        o, e = p.communicate()
#        if p.returncode :
#            raise (o, e, p.returncode)
#
#        db_url = 'http://localhost:5984'
#        reconstruction.insert_mesh(db_url, str(session.object_id), session.id, meshed_ply, surfel_ply)

if "__main__" == __name__:
    args = parse_args()
    couch = couchdb.Server(args.db_root)
    dbs = dbtools.init_object_databases(couch)
    sessions = dbs['sessions']
    if args.compute_all:
        models.sync_models(dbs)
        results = models.Session.all(sessions)
        for session in results:
            mesh_session(session, args)
    else:
        session = models.Session.load(sessions, args.session_id)
        if session == None or session.id == None:
            print "Could not load session with id:", args.session_id
            sys.exit(1)
        mesh_session(session, args)
