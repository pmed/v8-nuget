#!/usr/bin/env python

import glob
import os
import re
import string
import sys
import subprocess
import shutil

V8_URL = 'https://chromium.googlesource.com/v8/v8.git'
V8_VERSION = sys.argv[1] if len(sys.argv) > 1 else 'HEAD'

PLATFORMS = ['x86',
 #'x64'
 ]
CONFIGURATIONS = ['Debug', 'Release']

NUGET = os.path.join(os.environ['LOCALAPPDATA'], 'nuget', 'NuGet.exe')

def git_fetch(url, target):
	parts = url.split('.git@')
	if len(parts) > 1:
		url = parts[0] + '.git'
		ref = parts[1]
	else:
		ref = 'HEAD'
	print 'Fetch %s@%s to %s' % (url, ref, target)

#	if not os.path.isdir(os.path.join(target, '.git')):
#		subprocess.call(['git', 'init', target])
#	subprocess.call(['git', 'fetch', '--depth=1', url, ref], cwd=target)
#	subprocess.call(['git', 'checkout', '-B', 'Branch_' + ref, 'FETCH_HEAD'], cwd=target)

def v8_version():
	text = open('v8/include/v8-version.h').read()
	value = lambda name: re.search('^#define\s+'+name+'\s+(\d+)$', text, re.M).group(1)
	defines = ['V8_MAJOR_VERSION', 'V8_MINOR_VERSION', 'V8_BUILD_NUMBER', 'V8_PATCH_LEVEL']
	return string.join(map(value, defines), '.')

def vcx_toolset():
	text = open('v8/src/v8.vcxproj').read()
	return re.search('<PlatformToolset>(v\d+)</PlatformToolset>', text).group(1)

def copytree(src_dir, dest_dir):
	if not os.path.isdir(dest_dir):
		os.makedirs(dest_dir)
	for path in glob.iglob(src_dir):
		shutil.copy(path, dest_dir)


# __main__

## Fetch V8 sources
git_fetch(V8_URL + '@' + V8_VERSION, 'v8')
## Fetch V8 source dependencies
Var = lambda name: vars[name]
deps = open('v8/DEPS').read()
exec deps
for dep in ['v8/base/trace_event/common', 'v8/build', 'v8/testing/gtest', 'v8/tools/gyp', 'v8/tools/clang', 'v8/third_party/icu']:
	git_fetch(deps[dep], dep)
### Get v8 version from defines in v8-version.h
version = v8_version()
toolset=None

## Build V8
for arch in PLATFORMS:
	gyp_arch = 'ia32' if arch == 'x86' else arch
	gyp_args = ['-fmsvs', '-Dtarget_arch='+gyp_arch, '--depth=.',
		'-I./gypfiles/standalone.gypi', '-I../v8_options.gypi',
		'src/v8.gyp'
	]
	subprocess.call([sys.executable, 'tools/gyp/gyp_main.py'] + gyp_args, cwd='v8')
	### Get Visual C++ toolset from generated project file v8.vcxproj
	if not toolset:
		toolset = vcx_toolset()
	for conf in CONFIGURATIONS:
		print 'Build V8', version, arch, conf
		msbuild_platform = 'Win32' if arch == 'x86' else arch
		#build_args = ['/m', '/t:Rebuild', '/p:Configuration='+conf, '/p:Platform='+msbuild_platform]
		build_args = ['/m', '/p:Configuration='+conf, '/p:Platform='+msbuild_platform]
		subprocess.call(['msbuild', 'src\\v8.sln'] + build_args, cwd='v8')
		### Save build result
		dest_dir = os.path.join('v8/lib', toolset, arch, conf)
		if os.path.isdir(dest_dir):
			shutil.rmtree(dest_dir)
		copytree(os.path.join('v8/build', conf, 'lib', 'v8.*'), dest_dir) # .lib and .exp
		copytree(os.path.join('v8/build', conf, 'v8.*'), dest_dir) # .dll and .pdb
		copytree(os.path.join('v8/build', conf, 'v8_lib*.lib'), dest_dir)
		copytree(os.path.join('v8/build', conf, 'icu*.*'), dest_dir) # .dll, .pdb, .dat
	### Generate v8.targets file for the arch
	for name in ['v8', 'v8.redist', 'v8.symbols']:
		targets = open('nuget/{}-{}.props'.format(name, arch)).read()
		targets = targets.replace('$PlatformToolset$', toolset)
		open('nuget/{}-{}-{}.props'.format(name, toolset, arch), 'w+').write(targets)


# Make redist and symbol packages
nuget_args = [
	'-NoPackageAnalysis',
	'-Version', version,
	'-Properties', 'Platform='+arch+';PlatformToolset='+toolset,
	#'-OutputDirectory', 'nuget'
]
for arch in PLATFORMS:
	print 'NuPkg redist V8', version, toolset, arch
	for nuspec in ['v8.redist.nuspec', 'v8.symbols.nuspec']:
		subprocess.call([NUGET, 'pack', nuspec] + nuget_args, cwd='nuget')


# Make dev package
print 'NuPkg dev V8', version, toolset
subprocess.call([NUGET, 'pack', 'v8.nuspec'] + nuget_args, cwd='nuget')
