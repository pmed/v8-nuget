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
elif V8_VERSION.count('.') < 2 and all(x.isdigit() for x in V8_VERSION.split('.')):
	V8_VERSION += '-lkgr' 


PLATFORM = sys.argv[2] if len(sys.argv) > 2 else os.environ.get('PLATFORM', '')
PLATFORMS = [PLATFORM] if PLATFORM else ['x86', 'x64']

CONFIGURATION = sys.argv[3] if len(sys.argv) > 3 else os.environ.get('CONFIGURATION', '')
CONFIGURATIONS = [CONFIGURATION] if CONFIGURATION else ['Debug', 'Release']

XP_TOOLSET = (sys.argv[4] if len(sys.argv) > 4 else os.environ.get('XP')) == '1'

PACKAGES = ['v8', 'v8.redist', 'v8.symbols']

BIN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bin')
GN = os.path.join(BIN_DIR, 'gn.exe')
NINJA = os.path.join(BIN_DIR, 'ninja.exe')

def git_fetch(url, target):
	if isinstance(url, dict):
		#url = url['url']
		#if url['condition'] == 'checkut_android':
		return
	parts = url.split('.git@')
	if len(parts) > 1:
		url = parts[0] + '.git'
		ref = parts[1]
	else:
		ref = 'HEAD'
	print 'Fetch {}@{} into {}'.format(url, ref, target)

	if not os.path.isdir(os.path.join(target, '.git')):
		subprocess.check_call(['git', 'init', target])
	fetch_args = ['git', 'fetch', '--depth=1', '--update-shallow', '--update-head-ok', '--quiet', url, ref]
	if subprocess.call(fetch_args, cwd=target) != 0:
		print 'RETRY:', target
		shutil.rmtree(target, ignore_errors=True)
		subprocess.check_call(['git', 'init', target])
		subprocess.check_call(fetch_args, cwd=target)
	subprocess.check_call(['git', 'checkout', '-f', '-B', 'Branch_'+ref, 'FETCH_HEAD'], cwd=target)

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
version = string.join(map(lambda name: re.search(r'^#define\s+'+name+r'\s+(\d+)$', v8_version_h, re.M).group(1), \
	['V8_MAJOR_VERSION', 'V8_MINOR_VERSION', 'V8_BUILD_NUMBER', 'V8_PATCH_LEVEL']), '.')

vs_versions = {
	'12.0': { 'version': '2013', 'toolset': 'v120' },
	'14.0': { 'version': '2015', 'toolset': 'v140' },
	'15.0': { 'version': '2017', 'toolset': 'v141' },
}
vs_version = vs_versions[os.environ.get('VisualStudioVersion', '14.0')]
toolset = vs_version['toolset']
vs_version = vs_version['version']
vs_install_dir = os.path.abspath(os.path.join(os.environ['VCINSTALLDIR'], os.pardir))

env = os.environ.copy()
env['SKIP_V8_GYP_ENV'] = '1'
env['DEPOT_TOOLS_WIN_TOOLCHAIN'] = '0'
env['GYP_MSVS_VERSION'] = vs_version
env['GYP_MSVS_OVERRIDE_PATH'] = vs_install_dir

print '------------------------------------------------------'
print 'Environment Variables Set:'
print '  set SKIP_V8_GYP_ENV=', env['SKIP_V8_GYP_ENV']
print '  set DEPOT_TOOLS_WIN_TOOLCHAIN=', env['DEPOT_TOOLS_WIN_TOOLCHAIN']
print '  set GYP_MSVS_VERSION=', env['GYP_MSVS_VERSION']
print '  set GYP_MSVS_OVERRIDE_PATH=', env['GYP_MSVS_OVERRIDE_PATH']
print '------------------------------------------------------'

if XP_TOOLSET:
	env['INCLUDE'] = r'%ProgramFiles(x86)%\Microsoft SDKs\Windows\7.1A\Include;' + env.get('INCLUDE', '')
	env['PATH'] = r'%ProgramFiles(x86)%\Microsoft SDKs\Windows\7.1A\Bin;' + env.get('PATH', '')
	env['LIB'] = r'%ProgramFiles(x86)%\Microsoft SDKs\Windows\7.1A\Lib;' + env.get('LIB', '')
	env['CL'] = '/D_USING_' + toolset.upper() + '_SDK71_;' + env.get('CL', '')
	toolset += '_xp'

if toolset == 'v141':
	is_clang = 'false'
else:
	subprocess.check_call([sys.executable, 'tools/clang/scripts/update.py'], cwd='v8', env=env)
	# v8/build/vs_toolchain.py _CopyPGORuntime() supports only default version Visual Studio 2017
	del env['GYP_MSVS_VERSION']
	del env['GYP_MSVS_OVERRIDE_PATH']
	is_clang = 'true'


print 'V8 version', version
print 'Visual Studio', vs_version, 'in', vs_install_dir
print 'C++ Toolset', toolset

# Copy GN to the V8 buildtools in order to work v8gen script
shutil.copy(GN, 'v8/buildtools/win')

## Build V8
for arch in PLATFORMS:
#	if 'CLANG_TOOLSET' in env:
#		prefix = 'amd64' if arch == 'x64' else arch
#		env['PATH'] = os.path.join(vs_install_dir, r'VC\ClangC2\bin', prefix, prefix) + ';' + env.get('PATH', '')

	for conf in CONFIGURATIONS:
		### Generate build.ninja files in out.gn/toolset/arch/conf directory
		out_dir = os.path.join(toolset, arch, conf)
		builder = ('ia32' if arch == 'x86' else arch) + '.' + conf.lower()
		cmd = 'tools/dev/v8gen.py -b ' + builder + ' ' + out_dir +  ' -vv -- is_clang=' + is_clang + ' is_component_build=true treat_warnings_as_errors=false'

		print 'CMD: ', cmd, 'cwd: v8'
		
		subprocess.check_call([sys.executable, 'tools/dev/v8gen.py',
			'-b', builder, out_dir, '-vv', '--', 'is_clang='+is_clang, 'is_component_build=true', 'treat_warnings_as_errors=false'], cwd='v8', env=env)
		### Build V8 with ninja from the generated files
		out_dir = os.path.join('out.gn', out_dir)
		subprocess.check_call([NINJA, '-C', out_dir, 'v8'], cwd='v8', env=env)

	if arch == 'x86':
		platform = "('$(Platform)' == 'x86' Or '$(Platform)' == 'Win32')"
	else:
		platform = "'$(Platform)' == '{}'".format(arch)
	condition = "'$(PlatformToolset)' == '{}' And {}".format(toolset, platform)

	## Build NuGet packages
	for name in PACKAGES:
		## Generate property sheets with specific conditions
		props = open('nuget/{}.props'.format(name)).read()
		props = props.replace('$Condition$', condition)
		open('nuget/{}-{}-{}.props'.format(name, toolset, arch), 'w+').write(props)

		nuspec = name + '.nuspec'
		print 'NuGet pack {} for V8 {} {} {}'.format(nuspec, version, toolset, arch)
		nuget_args = [
			'-NoPackageAnalysis',
			'-Version', version,
			'-Properties', 'Platform='+arch+';PlatformToolset='+toolset,
			'-OutputDirectory', '..'
		]
		print 'CMD: ', ['nuget', 'pack ', nuspec] + nuget_args
		subprocess.check_call(['nuget', 'pack', nuspec] + nuget_args, cwd='nuget')

		os.remove('nuget/{}-{}-{}.props'.format(name, toolset, arch))
