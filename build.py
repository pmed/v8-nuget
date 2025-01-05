#!/usr/bin/env python

import argparse
import glob
import json
import os
import re
import string
import sys
import subprocess
import shutil
import urllib.request
import io
import zipfile
from pathlib import Path


BIN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bin')
GN_OPTIONS = {
	'v8_use_external_startup_data' : False,
	#'v8_generate_external_defines_header': True, # TODO: enable it later
	'is_clang': True,
	'use_lld': False,
	'use_custom_libcxx_for_host' : False,
	'use_custom_libcxx' : False,
	'treat_warnings_as_errors' : False,
	'fatal_linker_warnings' : False,
}

def parse_to_dict(action, parser, namespace, values, option_string):
	dict = getattr(namespace, action.dest, {})
	for item in values:
		key, value = item.split('=', 1)
		# distutils.util.strtobool treats 0/1 also as bool values
		try:
			dict[key] = int(value)
		except:
			if value.lower() in ['true', 'yes', 'on']:
				dict[key] = True
			elif value.lower() in ['false', 'no', 'off']:
				dict[key] = False
			else:
				dict[key] = value
	setattr(namespace, action.dest, dict)

arg_parser = argparse.ArgumentParser(description='Build V8 from sources', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
arg_parser.add_argument('--version',
	dest='V8_VERSION',
	default='lkgr',
	help='Version tag or branch name')
arg_parser.add_argument('--platform',
	dest='PLATFORMS',
	nargs='+',
	choices=['x86', 'x64'],
	default=['x86', 'x64'],
	help='Target platforms')
arg_parser.add_argument('--config',
	dest='CONFIGURATIONS',
	nargs='+',
	choices=['Debug', 'Release'],
	default=['Debug', 'Release'],
	help='Target configrations')
arg_parser.add_argument('--libs',
	dest='LIBS',
	nargs='+',
	choices=['shared', 'monolith'],
	default=['shared', 'monolith'],
	help='Target libraries')
arg_parser.add_argument('--gn-option',
	dest='GN_OPTIONS',
	nargs="+", metavar="KEY=VAL",
	action=type('', (argparse.Action, ), dict(__call__ = parse_to_dict)),
	default=GN_OPTIONS,
	help='Add gn option')

args = arg_parser.parse_args()


# Use only Last Known Good Revision branches
if args.V8_VERSION.count('.') < 2 and all(x.isdigit() for x in args.V8_VERSION.split('.')):
	args.V8_VERSION += '-lkgr' 


print('Parsed args: ', args)

vs_versions = {
	'16.0': { 'version': '2019', 'toolset': 'v142' },
	'17.0': { 'version': '2022', 'toolset': 'v143' },
}
vs_version = vs_versions[os.environ.get('VisualStudioVersion', '17.0')]
toolset = vs_version['toolset']
vs_version = vs_version['version']

#  VC build tools
vc_tools_install_dir = os.environ.get('VCToolsInstallDir')
if vc_tools_install_dir:
	vs_install_dir = vc_tools_install_dir
else:
	vs_install_dir = os.path.abspath(os.path.join(os.environ['VCINSTALLDIR'], os.pardir))

print(f'Visual Studio {vs_version} in {vs_install_dir}')
print(f'C++ Toolset {toolset}')


# Download depot_tools
if not os.path.isdir('depot_tools'):
	print('Downloading depot_tools')
	with urllib.request.urlopen('https://storage.googleapis.com/chrome-infra/depot_tools.zip') as resp:
		with zipfile.ZipFile(io.BytesIO(resp.read())) as zip:
			zip.extractall('depot_tools')

env = os.environ.copy()
#env['DEPOT_TOOLS_UPDATE'] = '0'
env['DEPOT_TOOLS_WIN_TOOLCHAIN'] = '0'


# Fetch V8 and dependencies
print('Fetching v8')
subprocess.check_call([os.path.join('depot_tools', 'gclient'), 'sync', '--no-history', '--shallow', '--gclientfile=v8.gclient', '--revision=' + args.V8_VERSION], env=env, shell=True)


### Get actual v8 version from defines in v8-version.h
v8_version_h = open('v8/include/v8-version.h').read()
version = '.'.join(map(lambda name: re.search(r'^#define\s+'+name+r'\s+(\d+)$', v8_version_h, re.M).group(1), \
	['V8_MAJOR_VERSION', 'V8_MINOR_VERSION', 'V8_BUILD_NUMBER', 'V8_PATCH_LEVEL']))
print(f'V8 {version}')


def cpp_defines_from_v8_json_build_config(out_dir):
	# TODO: use v8-gn.h instead

	def read_json(filename):
		result = dict()
		if os.path.isfile(filename):
			with open(os.path.join(out_dir, filename)) as file:
				result = json.load(file)
		return result

	config = read_json('v8_build_config.json') | read_json('v8_features.json')

	# see `enabled_external_v8_defines`, `enabled_external_cppgc_defines` in v8/BUILD.gn
	enabled_external_v8_defines = {
		'is_debug': 'V8_ENABLE_CHECKS',
		'is_full_debug': 'V8_ENABLE_CHECKS',
		'v8_enable_v8_checks': 'V8_ENABLE_CHECKS',
		'v8_enable_sandbox': 'V8_ENABLE_SANDBOX',
		'sandbox': 'V8_ENABLE_SANDBOX',
		'v8_enable_31bit_smis_on_64bit_arch': 'V8_31BIT_SMIS_ON_64BIT_ARCH',
		'v8_enable_pointer_compression': ['V8_COMPRESS_POINTERS', 'V8_31BIT_SMIS_ON_64BIT_ARCH'],
		'pointer_compression': ['V8_COMPRESS_POINTERS', 'V8_31BIT_SMIS_ON_64BIT_ARCH'],
		'v8_enable_zone_compression': 'V8_COMPRESS_ZONES',
		'v8_deprecation_warnings': 'V8_DEPRECATION_WARNINGS',
		'v8_imminent_deprecation_warnings': 'V8_IMMINENT_DEPRECATION_WARNINGS',
		'v8_use_perfetto': 'V8_USE_PERFETTO',
		'v8_enable_map_packing': 'V8_MAP_PACKING',
		'is_tsan': 'V8_IS_TSAN',
		'v8_enable_conservative_stack_scanning': 'V8_ENABLE_CONSERVATIVE_STACK_SCANNING',
		'v8_enable_direct_handle': 'V8_ENABLE_DIRECT_HANDLE',
		'v8_shortcut_strings_in_minor_ms': 'V8_MINORMS_STRING_SHORTCUTTING',
		'cppgc_enable_object_names': 'CPPGC_SUPPORTS_OBJECT_NAMES',
		'cppgc_enable_caged_heap': 'CPPGC_CAGED_HEAP',
		'cppgc_enable_young_generation': 'CPPGC_YOUNG_GENERATION',
		'cppgc_enable_pointer_compression': 'CPPGC_POINTER_COMPRESSION',
		'cppgc_enable_2gb_cage': 'CPPGC_2GB_CAGE',
		'cppgc_enable_larger_cage': 'CPPGC_ENABLE_LARGER_CAGE',
		'cppgc_enable_slim_write_barrier': 'CPPGC_SLIM_WRITE_BARRIER',

	}

	defines = set()
	for name, value in enabled_external_v8_defines.items():
		if config.get(name, False):
			defines.add(value)
	return ';'.join(defines)


def build(target, options, work_dir, out_dir, env):
	gn_args = list()
	for k, v in options.items():
		q = '"' if isinstance(v, str) else ''
		gn_args.append(k + '=' + q + str(v) + q)

	gn = os.path.join(os.getcwd(), 'v8', 'buildtools', 'win', 'gn.exe')
	ninja = os.path.join(os.getcwd(), 'v8', 'third_party', 'ninja', 'ninja.exe')

	subprocess.check_call([gn, 'gen', out_dir, '--args=' + ' '.join(gn_args).lower()], cwd=work_dir, env=env, shell=True)
	subprocess.check_call([ninja, '-C', out_dir, target], cwd=work_dir, env=env, shell=True)


def generate_abseil_exports(options, out_dir, env):
	# See _GenerateDefFile in v8/third_party/abseil-cpp/generate_def_files.py
	abseil = os.path.join('v8', 'third_party', 'abseil-cpp')
	if not os.path.isdir(abseil) or not options.get('is_component_build') or not options.get('is_clang') or options.get('use_custom_libcxx_for_host', True) or options.get('use_custom_libcxx', True):
		return

	arch = options['target_cpu']
	conf = 'dbg' if options['is_debug'] else 'rel'
	symbols_def = os.path.join(abseil, f'symbols_{arch}_{conf}.def')
	print (f'Updating {symbols_def}')

	# Build abseil objects
	absl_out_dir = os.path.join(out_dir, 'absl_component_deps')
	build('third_party/abseil-cpp:absl_component_deps', options, work_dir=abseil, out_dir=absl_out_dir, env=env)
	obj_dir=os.path.join(absl_out_dir, 'obj', 'third_party', 'abseil-cpp')

	# Read abseil symbols from the obj files
	files = list(Path(obj_dir).rglob('*.obj'))
	print(f'Reading {len(files)} *.obj files in {obj_dir}')

	# Typical dumpbin /symbol lines look like this:
	# 04B 0000000C SECT14 notype       Static       | ?$S1@?1??SetCurrent
	# ThreadIdentity@base_internal@absl@@YAXPAUThreadIdentity@12@P6AXPAX@Z@Z@4IA
	#  (unsigned int `void __cdecl absl::base_internal::SetCurrentThreadIdentity...
	# We need to start on "| ?" and end on the first " (" (stopping on space would
	# also work).
	# This regex is identical inside the () characters except for the ? after .*,
	# which is needed to prevent greedily grabbing the undecorated version of the
	# symbols.
	ABSL_SYM_RE = r'.*External     \| (?P<symbol>[?]+[^?].*?absl.*?|_?Absl.*?)($| \(.*)'
	# Typical exported symbols in dumpbin /directives look like:
	#    /EXPORT:?kHexChar@numbers_internal@absl@@3QBDB,DATA
	ABSL_EXPORTED_RE = r'.*/EXPORT:(.*),.*'

	absl_symbols = set()
	dll_exports = set()

	for file in files:
		# Track all of the functions exported with __declspec(dllexport) and
		# don't list them in the .def file - double-exports are not allowed. The
		# error is "lld-link: error: duplicate /export option".
		stdout = subprocess.check_output(['dumpbin', '/directives', file])
		for line in stdout.splitlines():
			line = line.decode('utf-8')
			match = re.match(ABSL_EXPORTED_RE, line)
			if match:
				dll_exports.add(match.groups()[0])
	print(f'Found {len(dll_exports)} already exported symbols')

	for file in files:
		stdout = subprocess.check_output(['dumpbin', '/symbols', file])
		for line in stdout.splitlines():
			try:
				line = line.decode('utf-8')
			except UnicodeDecodeError:
				# Due to a dumpbin bug there are sometimes invalid utf-8 characters in
				# the output. This only happens on an unimportant line so it can
				# safely and silently be skipped.
				# https://developercommunity.visualstudio.com/content/problem/1091330/dumpbin-symbols-produces-randomly-wrong-output-on.html
				continue
			match = re.match(ABSL_SYM_RE, line)
			if match:
				symbol = match.group('symbol')
				assert symbol.count(' ') == 0, ('Regex matched too much, probably got undecorated name as well')
				# Avoid getting names exported with dllexport, to avoid
				# "lld-link: error: duplicate /export option" on symbols such as:
				# ?kHexChar@numbers_internal@absl@@3QBDB
				if symbol in dll_exports:
					continue
				# Avoid to export deleting dtors since they trigger
				# "lld-link: error: export of deleting dtor" linker errors, see
				# crbug.com/1201277.
				if symbol.startswith('??_G'):
					continue
				# Strip any leading underscore for C names (as in __cdecl). It's only
				# there on x86, but the x86 toolchain falls over when you include it!
				if arch == 'x86' and symbol.startswith('_'):
					symbol = symbol[1:]
				absl_symbols.add(symbol)
	print(f'Found {len(absl_symbols)} absl symbols')

	with open(symbols_def, 'w', newline='') as file:
		file.write('EXPORTS\n')
		for s in sorted(absl_symbols):
			file.write(f'    {s}\n')


PACKAGES = {
	'shared' : ['v8', 'v8.redist', 'v8.symbols'],
	'monolith' : ['v8.monolith'],
}

## Build V8
for arch in args.PLATFORMS:
	arch = arch.lower()
	for lib in args.LIBS:
		cpp_defines = ''
		for conf in args.CONFIGURATIONS:
			### Generate build.ninja files in v8/out.gn/V8_VERSION/toolset/arch/conf/lib directory
			out_dir = os.path.join(os.getcwd(), 'v8', 'out.gn', args.V8_VERSION, toolset, arch, conf, lib)
			options = args.GN_OPTIONS
			options['is_debug'] = (conf == 'Debug')
			options['target_cpu'] = arch
			options['is_component_build'] = (lib == 'shared')
			options['v8_monolithic'] = (lib == 'monolith')

			generate_abseil_exports(options, out_dir=out_dir, env=env)
			build('v8' if lib == 'shared' else 'v8_monolith', options, work_dir='v8', out_dir=out_dir, env=env)

			cpp_defines += """
	<PreprocessorDefinitions Condition="'$(Configuration)' == '{conf}'">{defines};%(PreprocessorDefinitions)</PreprocessorDefinitions>
	""".format(conf=conf, defines=cpp_defines_from_v8_json_build_config(out_dir))

		if arch == 'x86':
			platform = "('$(Platform)' == 'x86' Or '$(Platform)' == 'Win32')"
		else:
			platform = f"'$(Platform)' == '{arch}'"
		condition = f"'$(PlatformToolset)' == '{toolset}' And {platform}"

		## Build NuGet packages
		for name in PACKAGES[lib]:
			## Generate property sheets with specific conditions
			props = open(f'nuget/{name}.props').read()
			props = props.replace('$Condition$', condition)
			if cpp_defines:
				 props = props.replace('<PreprocessorDefinitions />', cpp_defines)
			open(f'nuget/{name}-{toolset}-{arch}.props', 'w+').write(props)

			nuspec = name + '.nuspec'
			print(f'NuGet pack {nuspec} for V8 {version} {toolset} {arch}')
			nuget_args = [
				'-NoPackageAnalysis',
				'-Version', version,
				'-Properties', 'Platform='+arch+';PlatformToolset='+toolset+';BuildVersion='+args.V8_VERSION,
				'-OutputDirectory', '..'
			]
			subprocess.check_call(['nuget', 'pack', nuspec] + nuget_args, cwd='nuget')
			os.remove(f'nuget/{name}-{toolset}-{arch}.props')
