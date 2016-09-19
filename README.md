# NuGet package for V8 JavaScript Engine

This package contains prebuild V8 binaries, debug symbols, headers and
libraries required to embed the V8 JavaScript engine into a C++ project.

| Package                     | Version
|-----------------------------|----------------------------------------------------------------------------------------------------------------------|
|V8 x86 for Visual Studio 2013|[![NuGet](https://img.shields.io/nuget/v/v8-v120-x86.svg?maxAge=2592000)](https://www.nuget.org/packages/v8-v120-x86/)|
|V8 x86 for Visual Studio 2015|[![NuGet](https://img.shields.io/nuget/v/v8-v140-x86.svg?maxAge=2592000)](https://www.nuget.org/packages/v8-v140-x86/)|
|V8 x64 for Visual Studio 2013|[![NuGet](https://img.shields.io/nuget/v/v8-v120-x64.svg?maxAge=2592000)](https://www.nuget.org/packages/v8-v120-x64/)|
|V8 x64 for Visual Studio 2015|[![NuGet](https://img.shields.io/nuget/v/v8-v140-x64.svg?maxAge=2592000)](https://www.nuget.org/packages/v8-v140-x64/)|


## Usage

To use V8 in a project install the package `v8-$PlatformToolset-$Platform.$Version`
from a console with `nuget install` commmand or from inside of Visual Studio
(see menu option *Tools -> NuGet Package Manager -> Manage NuGet Packages for Solution...*)
where

  * `$PlatformToolset` is the C++ toolset version used in Visual Studio:
    * `v120` - for Visual Studio 2013
    * `v140` - for Visual Studio 2015
  
  * `$Platform` is a target platform type, currently `x86` or `x64`.

  * `$Version` is the actual V8 version, one of https://chromium.googlesource.com/v8/v8.git/+refs


After successful package installation add `#include <v8.h>` in a C++ 
project and build it. All neccessary files (*.lib, *.dll, *.pdb) should be
referenced in the project automatically with MsBuild property sheets.

## How to build

This section is mostly for the package maintainers who wants to update V8.

Tools required to build V8 NuGet package on Windows:

  * Visual C++ toolset (version >=2013)
  * Python 2.X
  * Git
  * NuGet (https://dist.nuget.org/index.html)

To build V8 and make NuGet packages:

  1. Run `build.py` with optional V8 version argument.
  2. Publish `nuget/*.nupkg` files after successful build.
