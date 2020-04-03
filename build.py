#!/usr/bin/env python

import glob
import json
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
USE_CLANG = (sys.argv[5] if len(sys.argv) > 5 else os.environ.get('USE_CLANG', '1')) == '1'

PACKAGES = ['v8', 'v8.redist', 'v8.symbols']

BIN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bin')
GN = os.path.join(BIN_DIR, 'gn.exe')
NINJA = os.path.join(BIN_DIR, 'ninja.exe')

GN_OPTIONS = [
	'is_component_build=true',
	'treat_warnings_as_errors=false',
	'fatal_linker_warnings=false',
	#'use_jumbo_build=true', # removed in V8 version 8.1
	#'symbol_level=1',
	'v8_enable_fast_mksnapshot=true',
	'v8_enable_fast_torque=true',
	'v8_enable_verify_heap=false', # to fix VC++ Linker error in Debug configuratons
	#'v8_optimized_debug=false',
	#'v8_use_snapshot=true',
	#'v8_use_external_startup_data=false',
	#'v8_enable_handle_zapping=true',
	#'v8_check_header_includes=true',
	#'v8_win64_unwinding_info=false',
	#'dcheck_always_on=true',
]

if USE_CLANG:
	GN_OPTIONS.extend(['is_clang=true', 'use_custom_libcxx=false'])
else:
	GN_OPTIONS.extend(['is_clang=false'])


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

## Fetch only required V8 source dependencies
required_deps = [
	'v8/build',
	'v8/third_party/icu',
	'v8/base/trace_event/common',
	'v8/third_party/jinja2',
	'v8/third_party/markupsafe',
	'v8/third_party/googletest/src',
	'v8/third_party/zlib',
]

if USE_CLANG:
	required_deps.append('v8/tools/clang')

Var = lambda name: vars[name]
deps = open('v8/DEPS').read()
exec deps
for dep in deps:
	if dep in required_deps:
		git_fetch(deps[dep], dep)

### Get v8 version from defines in v8-version.h
v8_version_h = open('v8/include/v8-version.h').read()
version = string.join(map(lambda name: re.search(r'^#define\s+'+name+r'\s+(\d+)$', v8_version_h, re.M).group(1), \
	['V8_MAJOR_VERSION', 'V8_MINOR_VERSION', 'V8_BUILD_NUMBER', 'V8_PATCH_LEVEL']), '.')

vs_versions = {
	'12.0': { 'version': '2013', 'toolset': 'v120' },
	'14.0': { 'version': '2015', 'toolset': 'v140' },
	'15.0': { 'version': '2017', 'toolset': 'v141' },
	'16.0': { 'version': '2019', 'toolset': 'v142' },
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

#  old VC build tools?
vc_tools_install_dir = os.environ.get('VCToolsInstallDir')
if vc_tools_install_dir:
	vs_install_dir = vc_tools_install_dir
vc_tools_version = os.environ.get('VCToolsVersion')
if vc_tools_version:
	vs_version = vc_tools_version
	toolset = 'v' + vs_version.replace('.', '')[:3]


if XP_TOOLSET:
	if toolset.startswith('v142'):
		raise RuntimeError("XP toolset is not supported")
	env['INCLUDE'] = r'%ProgramFiles(x86)%\Microsoft SDKs\Windows\7.1A\Include;' + env.get('INCLUDE', '')
	env['PATH'] = r'%ProgramFiles(x86)%\Microsoft SDKs\Windows\7.1A\Bin;' + env.get('PATH', '')
	env['LIB'] = r'%ProgramFiles(x86)%\Microsoft SDKs\Windows\7.1A\Lib;' + env.get('LIB', '')
	toolset += '_xp'

subprocess.check_call([sys.executable, 'vs_toolchain.py', 'update'], cwd='v8/build', env=env)
if USE_CLANG:
	subprocess.check_call([sys.executable, 'update.py'], cwd='v8/tools/clang/scripts', env=env)

#import pprint
#pprint.pprint(env)

print 'V8 version', version
print 'Visual Studio', vs_version, 'in', vs_install_dir
print 'C++ Toolset', toolset

# Copy GN to the V8 buildtools in order to work v8gen script
if not os.path.exists('v8/buildtools/win'):
    os.makedirs('v8/buildtools/win')
shutil.copy(GN, 'v8/buildtools/win')

# Generate LASTCHANGE file
# similiar to `lastchange` hook from DEPS
if os.path.isfile('v8/build/util/lastchange.py'):
	subprocess.check_call([sys.executable, 'lastchange.py', '-o', 'LASTCHANGE'], cwd='v8/build/util', env=env)

def cpp_defines_from_v8_json_build_config(filename):
	json_file = open(filename)
	config = json.load(json_file)

	defines = set()
	if config.get('is_debug', False) or config.get('is_full_debug', False) or config.get('v8_enable_v8_checks', False):
		defines.add('V8_ENABLE_CHECKS')

	if config.get('v8_enable_pointer_compression', False):
		defines.add('V8_COMPRESS_POINTERS')
		defines.add('V8_31BIT_SMIS_ON_64BIT_ARCH')

	if config.get('v8_enable_31bit_smis_on_64bit_arch', False):
		defines.add('V8_31BIT_SMIS_ON_64BIT_ARCH')

	if config.get('v8_deprecation_warnings', False):
		defines.add('V8_DEPRECATION_WARNINGS')

	if config.get('v8_imminent_deprecation_warnings', False):
		defines.add('V8_IMMINENT_DEPRECATION_WARNINGS')

	return ';'.join(defines)


## Build V8
for arch in PLATFORMS:
#	if 'CLANG_TOOLSET' in env:
#		prefix = 'amd64' if arch == 'x64' else arch
#		env['PATH'] = os.path.join(vs_install_dir, r'VC\ClangC2\bin', prefix, prefix) + ';' + env.get('PATH', '')
	arch = arch.lower()
	cpp_defines = ''
	for conf in CONFIGURATIONS:
		### Generate build.ninja files in out.gn/V8_VERSION/toolset/arch/conf directory
		out_dir = os.path.join('out.gn', V8_VERSION, toolset, arch, conf)
		options = GN_OPTIONS
		options.append('is_debug=' + ('true' if conf == 'Debug' else 'false'))
		options.append('target_cpu="' + arch + '"')
		subprocess.check_call([GN, 'gen', out_dir, '--args='+' '.join(options)], cwd='v8', env=env)
		### Build V8 with ninja from the generated files
		subprocess.check_call([NINJA, '-C', out_dir, 'v8'], cwd='v8', env=env)
		cpp_defines += """
<PreprocessorDefinitions Condition="'$(Configuration)' == '{conf}'">{defines};%(PreprocessorDefinitions)</PreprocessorDefinitions>
""".format(conf=conf, defines=cpp_defines_from_v8_json_build_config(os.path.join('v8', out_dir, 'v8_build_config.json')))

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
		if cpp_defines:
			 props = props.replace('<PreprocessorDefinitions />', cpp_defines)
		open('nuget/{}-{}-{}.props'.format(name, toolset, arch), 'w+').write(props)

		nuspec = name + '.nuspec'
		print 'NuGet pack {} for V8 {} {} {}'.format(nuspec, version, toolset, arch)
		nuget_args = [
			'-NoPackageAnalysis',
			'-Version', version,
			'-Properties', 'Platform='+arch+';PlatformToolset='+toolset+';BuildVersion='+V8_VERSION,
			'-OutputDirectory', '..'
		]
		subprocess.check_call(['nuget', 'pack', nuspec] + nuget_args, cwd='nuget')
		os.remove('nuget/{}-{}-{}.props'.format(name, toolset, arch))
