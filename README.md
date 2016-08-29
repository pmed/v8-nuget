# NuGet package for V8 JavaScript Engine

## Building
Tools required to build V8 for Windows:

  * Visual C++ toolset (version >=2013)
  * Python 2.X
  * NuGet (https://dist.nuget.org/index.html)

1. Run `build.py` with optional V8 version argument.
2. After successful build publish `nuget/*.nupkg` files.

## Using the package

To use V8 in a project please install the package `v8-$PlatformToolset-$Platform.$version`
from a console with `nuget install` commmand or from inside of Visual Studio
(see menu option *Tools -> NuGet Package Manager -> Manage NuGet Packages for Solution...*)

  where

$PlatformToolset is a C++ toolset version used in Visual Studio:
  * `v120` - for Visual Studio 2013
  * `v140` - for Visual Studio 2015
  * `vXYZ` - for next Visual Studio version

$Platform is a target platfor type, currenlty `x86` and `x64`.

After successful package installation just #include <v8.h> in your C++ 
project and build it. All neccessary files (*.lib, *.dll, *.pdb) should be
referenced to the project automatically with MsBuild property sheets.