#!/usr/bin/env python3

#  SPDX-License-Identifier: GPL-3.0+
#
# Copyright © 2021 T. Beck.
#
# This file is part of DriftCheck.
#
# DriftCheck is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# DriftCheck is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with DriftCheck.  If not, see <http://www.gnu.org/licenses/>.

'''Visual inspection of detector drifts using GASPware data'''

import os
import re
import sys
import copy
import subprocess

import argparse as ap
import numpy as np
import matplotlib.pyplot as plt

from matplotlib import cm
from matplotlib.colors import LogNorm
from tqdm.auto import tqdm

#---------------------------------------------------------------------------------------#
#		Commands cmat
#---------------------------------------------------------------------------------------#

def write_cmat_commands(in_run,in_args):
	'''Load matrices in cmat and gate on the individual detectors.
	Store the resulting 1d spetra in the current working directory
	(i.e. where drift_check.py is called).'''

	out_string  = 'cmat -l << echo\n'
	out_string += 'o %s\n'% in_run

	for det in range(in_args.num_dets):

		out_string += 'gate\n'
		out_string += '2\n'
		out_string += '\n'
		out_string += '%i %i\n'% (det,det)
		out_string += '\n'
		out_string += '\n'
		out_string += '%s_det%02i|l:8\n'% (in_run,det+1)

	out_string += 'q\necho'

	with open(os.path.join(in_args.head,'split_run.sh'),'w') as file:
		file.write(out_string)

	return

#---------------------------------------------------------------------------------------#
#		Split and convert matrices
#---------------------------------------------------------------------------------------#

def split_matrices(in_args):
	'''Identify all needed runs in the current working directory.
	Since cmat does not accept arbitrarily long path names for matrices,
	all cmat operations are performed in the data directory.
	Split and convert runs to .txt and move them to the destination directory.'''

	subprocess.call(['cd %s && chmod +x split_run.sh && ./split_run.sh'% in_args.head],
			shell=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

	runs_split	= [file for file in os.listdir(in_args.head)
				if re.search(in_args.tail+'[0-9]{3}_det[0-9]{2}$',file)]

	if runs_split == []:
		sys.exit('ERROR: Found no runs to split in path %s/.'% (in_args.head))

	for run in runs_split:

		subprocess.call(['mkascii16k %s %s'% (os.path.join(in_args.head,run),
				os.path.join(in_args.dest,run+'.txt'))],
				shell=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
		subprocess.call(['rm %s'% os.path.join(in_args.head,run)],
				shell=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

	return

#---------------------------------------------------------------------------------------#
#		Load spectra (.txt files)
#---------------------------------------------------------------------------------------#

def load_spectra(in_det,in_args):
	'''Load all run spectra for a given detector and store them in a matrix.
	Only take into account the requested range of the spectrum.'''

	#Identify files
	runs_txt 	= [os.path.join(in_args.dest,file) for file in os.listdir(in_args.dest)
				if re.search(in_args.tail+'[0-9]{3}_det%02i.txt$'% (in_det+1),file)]

	if runs_txt == []:
		sys.exit('ERROR: Found no ascii spectra in path %s.\
			Maybe run DriftCheck with option --full.'% (in_args.dest))

	#Initialize matrix
	max_run 	= np.max([int(re.search('[0-9]{3}(?=_det[0-9]+.txt$)',run).group(0)) 
					for run in runs_txt])
	matrix 		= np.zeros((max_run,int(np.diff(in_args.range))))

	for run in runs_txt:

		run_number 		= int(run.split('_')[-2])
		matrix[run_number-1]	= np.loadtxt(run,usecols=(1))[in_args.range[0]:in_args.range[1]]

	#Save matrix entries
	if args.write:
		np.savetxt(os.path.join(in_args.dest,in_args.tail+'det%02i.mat'% (in_det+1)),matrix.T)

	return max_run,matrix.T

#---------------------------------------------------------------------------------------#
#		Prepare plots
#---------------------------------------------------------------------------------------#

def prepare_plots(in_det,in_args):
	'''Prepare a spectrum-over-run number matrix for a given detector.'''

	#Load all runs
	max_run,matrix 	= load_spectra(in_det=in_det,in_args=in_args)

	#Modify colormap
	cmap = copy.copy(cm.viridis)
	cmap.set_under(color='white')

	#Prepare plot
	plt.figure(figsize=(10,5))

	plt.imshow(matrix,
		aspect='auto',
		origin='lower',
		extent=(0,max_run,in_args.range[0],in_args.range[1]),
		#interpolation='nearest',
		#cmap='viridis',
		cmap=cmap,
		norm=LogNorm(vmin=matrix[in_args.range[0]:in_args.range[1]].min()+1,
				vmax=matrix[in_args.range[0]:in_args.range[1]].max()),
		)

	plt.text(0.95*max_run,0.9*in_args.range[1],'Det %i'% (in_det+1),
				fontsize=20,color='white',ha='right',
				#bbox=dict(boxstyle='round',facecolor='white',edgecolor='white',alpha=0.5)
				)

	plt.xlim(0,max_run)
	plt.ylim(in_args.range[0],in_args.range[1])

	plt.xlabel('Run',fontsize=16)
	plt.ylabel('Channel',fontsize=16)
	plt.tick_params(axis='both',which='major',labelsize=16)

	plt.tight_layout()

	plt.savefig(os.path.join(in_args.dest,'det%i.pdf'% (in_det+1)))
	plt.close()

#---------------------------------------------------------------------------------------#
#		Main
#---------------------------------------------------------------------------------------#

#----- Parse arguments -----#

argparser = ap.ArgumentParser(description='Create spectra over run number from GASPware matrices.')

argparser.add_argument('pattern',	metavar='PATTERN',type=str,
					help='path to and name pattern of matrices')
argparser.add_argument('--full',	dest='full',action='store_true',
					help='create .txt files from matrices')
argparser.add_argument('--write',	dest='write',action='store_true',
					help='store raw data of plots in .mat files')
argparser.add_argument('--clear',	dest='clear',action='store_true',
					help='delete created .txt files')
argparser.add_argument('--dest',	dest='dest',metavar='DESTINATION',type=str,default=os.getcwd(),
					help='path where output is stored (default: current location)')
argparser.add_argument('--dets', 	dest='num_dets',metavar='NUM DETS',type=int,default=25,
					help='number of detectors (default: 25)')
argparser.add_argument('--range',	dest='range',metavar='RANGE',type=int,nargs=2,default=[0,8191],
					help='plot range for data axis (default: 0 8191)')

args		= argparser.parse_args()

#----- Separate file pattern and data path -----#

args.head 	= os.path.abspath(os.path.split(args.pattern)[0])
args.tail 	= os.path.split(args.pattern)[1]
args.dest	= os.path.abspath(args.dest)

#----- Create .txt files -----#

if args.full:

	#Identify files
	runs_cmat	= [file for file in os.listdir(args.head)
					if re.search(args.tail+'[0-9]{3}.cmat$',file)]

	if runs_cmat == []:
		sys.exit('ERROR: Found no files matching pattern %s in path %s/.'% (args.tail,args.head))

	print('Splitting matrices...')

	#Split matrices
	for run in tqdm(runs_cmat):

		write_cmat_commands(in_run=run.split('.')[0],in_args=args)
		split_matrices(in_args=args)

#----- Run for each detector -----#

print('Preparing plots...')

for det in tqdm(range(args.num_dets)):

	prepare_plots(in_det=det,in_args=args)

#----- Clear .txt files -----#

if args.clear:

	print('Cleaning up...')

	#Delete split_run.sh
	subprocess.call(['rm %s'% (os.path.join(args.head,'split_run.sh'))],
			shell=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

	#Delete .txt-files without exceeding the bash input limit
	files_txt 	= [file for file in os.listdir(args.dest)
				if re.search(args.tail+'[0-9]{3}_det[0-9]{2}.txt$',file)]

	subprocess.call(['cd %s && rm %s'% (args.dest,' '.join(files_txt))],
			shell=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
	
