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

BIN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bin')
GN_OPTIONS = {
	'v8_use_external_startup_data' : False,
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


def cpp_defines_from_v8_json_build_config(filename):
	json_file = open(filename)
	config = json.load(json_file)

	defines = set()
	if config.get('is_debug', False) or config.get('is_full_debug', False) or config.get('v8_enable_v8_checks', False):
		defines.add('V8_ENABLE_CHECKS')

	if config.get('v8_enable_sandbox', False) or config.get('sandbox', False):
		defines.add('V8_ENABLE_SANDBOX')

	if config.get('v8_enable_pointer_compression', False) or config.get('pointer_compression', False):
		defines.add('V8_COMPRESS_POINTERS')
		defines.add('V8_31BIT_SMIS_ON_64BIT_ARCH')

	if config.get('v8_enable_31bit_smis_on_64bit_arch', False):
		defines.add('V8_31BIT_SMIS_ON_64BIT_ARCH')

	if config.get('v8_deprecation_warnings', False):
		defines.add('V8_DEPRECATION_WARNINGS')

	if config.get('v8_imminent_deprecation_warnings', False):
		defines.add('V8_IMMINENT_DEPRECATION_WARNINGS')

	return ';'.join(defines)


def build(target, options, env, out_dir):
	gn_args = list()
	for k, v in options.items():
		q = '"' if isinstance(v, str) else ''
		gn_args.append(k + '=' + q + str(v) + q)
	subprocess.check_call([os.path.join('buildtools', 'win', 'gn.exe'), 'gen', out_dir, '--args=' + ' '.join(gn_args).lower()], cwd='v8', env=env, shell=True)
	subprocess.check_call([os.path.join('third_party', 'ninja', 'ninja.exe'), '-C', out_dir, target], cwd='v8', env=env, shell=True)


PACKAGES = {
	'shared' : ['v8', 'v8.redist', 'v8.symbols'],
	'monolith' : ['v8.monolith'],
}

## Build V8
for arch in args.PLATFORMS:
	arch = arch.lower()
	for lib in args.LIBS:
		cpp_defines = ''
		build_monolith = (lib == 'monolith')
		for conf in args.CONFIGURATIONS:
			### Generate build.ninja files in out.gn/V8_VERSION/toolset/arch/conf/lib directory
			out_dir = os.path.join('out.gn', args.V8_VERSION, toolset, arch, conf, lib)
			options = args.GN_OPTIONS
			options['is_debug'] = (conf == 'Debug')
			options['target_cpu'] = arch
			options['is_component_build'] = not build_monolith
			options['v8_monolithic'] = build_monolith
			target = 'v8'
			if build_monolith:
				target += '_monolith'
			build(target, options, env, out_dir)
			cpp_defines += """
	<PreprocessorDefinitions Condition="'$(Configuration)' == '{conf}'">{defines};%(PreprocessorDefinitions)</PreprocessorDefinitions>
	""".format(conf=conf, defines=cpp_defines_from_v8_json_build_config(os.path.join('v8', out_dir, 'v8_build_config.json')))

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
