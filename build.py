#!/usr/bin/env python

import glob
import os
import re
import string
import sys
import subprocess
import shutil

V8_URL = 'https://chromium.googlesource.com/v8/v8.git'
V8_VERSION = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('V8_VERSION', '')

# Use only Last Known Good Revision branches
if V8_VERSION == '':
	V8_VERSION = 'lkgr' 
elif V8_VERSION.count('.') < 3 and all(x.isdigit() for x in V8_VERSION.split('.')):
	V8_VERSION += '-lkgr' 


PLATFORM = sys.argv[2] if len(sys.argv) > 2 else os.environ.get('PLATFORM', '')
PLATFORMS = [PLATFORM] if PLATFORM else ['x86', 'x64']

CONFIGURATION = sys.argv[3] if len(sys.argv) > 3 else os.environ.get('CONFIGURATION', '')
CONFIGURATIONS = [CONFIGURATION] if CONFIGURATION else ['Debug', 'Release']


def git_fetch(url, target):
	parts = url.split('.git@')
	if len(parts) > 1:
		url = parts[0] + '.git'
		ref = parts[1]
	else:
		ref = 'HEAD'
	print 'Fetch {} into {}'.format(url, target)

	if not os.path.isdir(os.path.join(target, '.git')):
		subprocess.call(['git', 'init', target])
	subprocess.call(['git', 'fetch', '--depth=1', url, ref], cwd=target)
	subprocess.call(['git', 'checkout', '-f', '-B', 'Branch_'+ref, 'FETCH_HEAD'], cwd=target)

def rmtree(dir):
	if os.path.isdir(dir):
		shutil.rmtree(dir)

def copytree(src_dir, dest_dir):
	if not os.path.isdir(dest_dir):
		os.makedirs(dest_dir)
	for path in glob.iglob(src_dir):
		shutil.copy(path, dest_dir)


# __main__

## Fetch V8 sources
git_fetch(V8_URL+'@'+V8_VERSION, 'v8')

## Fetch V8 source dependencies besides tests
Var = lambda name: vars[name]
deps = open('v8/DEPS').read()
exec deps
for dep in deps:
	if not dep.startswith('v8/test/'):
		git_fetch(deps[dep], dep)

### Get v8 version from defines in v8-version.h
v8_version_h = open('v8/include/v8-version.h').read()
version = string.join(map(lambda name: re.search('^#define\s+'+name+'\s+(\d+)$', v8_version_h, re.M).group(1), \
	['V8_MAJOR_VERSION', 'V8_MINOR_VERSION', 'V8_BUILD_NUMBER', 'V8_PATCH_LEVEL']), '.')

toolset=None
vs_versions = { '12.0': '2013', '14.0': '2015' }
vs_version = vs_versions.get(os.environ.get('VisualStudioVersion'))

## Build V8
if os.path.isfile('v8/src/v8.gyp'):
	src_dir = 'src'
	v8_gyp_dir = 'gypfiles'
else:
	src_dir = 'tools/gyp'
	v8_gyp_dir = 'build'

for arch in PLATFORMS:
	gyp_arch = 'ia32' if arch == 'x86' else arch
	gyp_args = ['-fmsvs', '-Dtarget_arch='+gyp_arch,
		'-I../v8_options.gypi',
		src_dir + '/v8.gyp'
	]
	gyp_env = os.environ.copy()
	gyp_env['DEPOT_TOOLS_WIN_TOOLCHAIN'] = '0'
	if vs_version:
		gyp_env['GYP_MSVS_VERSION'] = vs_version
	else:
		gyp_env['SKIP_V8_GYP_ENV'] = '1'

	subprocess.call([sys.executable, v8_gyp_dir + '/gyp_v8'] + gyp_args, cwd='v8', env=gyp_env)

	### Get Visual C++ toolset from generated project file v8.vcxproj
	if not toolset:
		toolset = re.search('<PlatformToolset>(v\d+)</PlatformToolset>', \
			open(os.path.join('v8', src_dir, 'v8.vcxproj')).read()).group(1)

	### Build configurations for the current platform
	for conf in CONFIGURATIONS:
		print 'Build V8 {} {} {}'.format(version, arch, conf)
		build_dir = os.path.join('v8/build', conf)
		dest_dir = os.path.join('v8/lib', toolset, arch, conf)
		rmtree(build_dir)
		rmtree(dest_dir)
		msbuild_platform = 'Win32' if arch == 'x86' else arch
		build_args = ['/m', '/t:Rebuild', '/p:Configuration='+conf, '/p:Platform='+msbuild_platform]
		subprocess.call(['msbuild', src_dir +'\\v8.sln'] + build_args, cwd='v8')
		### Save build result
		for src in ['lib/v8.*', 'v8.*', 'v8_lib*', 'icu*.*']:
			copytree(os.path.join(build_dir, src), dest_dir)

	### Generate property sheets with specific conditions
	if arch == 'x86':
		platform = "('$(Platform)' == 'x86' Or '$(Platform)' == 'Win32')"
	else:
		platform = "'$(Platform)' == '{}'".format(arch)
	condition = "'$(PlatformToolset)' == '{}' And {}".format(toolset, platform)
	for name in ['v8', 'v8.redist', 'v8.symbols']:
		props = open('nuget/{}.props'.format(name)).read()
		props = props.replace('$Condition$', condition)
		open('nuget/{}-{}-{}.props'.format(name, toolset, arch), 'w+').write(props)


# Make packages
for arch in PLATFORMS:
	for nuspec in ['v8.nuspec', 'v8.redist.nuspec', 'v8.symbols.nuspec']:
		print 'NuGet pack {} for V8 {} {} {}'.format(nuspec, version, toolset, arch)
		nuget_args = [
			'-NoPackageAnalysis',
			'-Version', version,
			'-Properties', 'Platform='+arch+';PlatformToolset='+toolset,
			#'-OutputDirectory', 'nuget'
		]
		subprocess.call(['nuget', 'pack', nuspec] + nuget_args, cwd='nuget')
