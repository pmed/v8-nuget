# NuGet package for V8 JavaScript Engine

This packages contain prebuilt V8 binaries, debug symbols, headers and
libraries required to embed the V8 JavaScript engine into a C++ project.

| Package                     | Version
|-----------------------------|----------------------------------------------------------------------------------------------------------------------|
|V8 x86 for Visual Studio 2013|[![NuGet](https://img.shields.io/nuget/v/v8-v120-x86.svg)](https://www.nuget.org/packages/v8-v120-x86/)|
|V8 x86 for Visual Studio 2015|[![NuGet](https://img.shields.io/nuget/v/v8-v140-x86.svg)](https://www.nuget.org/packages/v8-v140-x86/)|
|V8 x86 for Visual Studio 2017|[![NuGet](https://img.shields.io/nuget/v/v8-v141-x86.svg)](https://www.nuget.org/packages/v8-v141-x86/)|
|V8 x64 for Visual Studio 2013|[![NuGet](https://img.shields.io/nuget/v/v8-v120-x64.svg)](https://www.nuget.org/packages/v8-v120-x64/)|
|V8 x64 for Visual Studio 2015|[![NuGet](https://img.shields.io/nuget/v/v8-v140-x64.svg)](https://www.nuget.org/packages/v8-v140-x64/)|
|V8 x64 for Visual Studio 2017|[![NuGet](https://img.shields.io/nuget/v/v8-v141-x64.svg)](https://www.nuget.org/packages/v8-v141-x64/)|
|V8 x86 for Visual Studio 2013 XP platform toolset|[![NuGet](https://img.shields.io/nuget/v/v8-v120_xp-x86.svg)](https://www.nuget.org/packages/v8-v120_xp-x86/)|
|V8 x86 for Visual Studio 2015 XP platform toolset|[![NuGet](https://img.shields.io/nuget/v/v8-v140_xp-x86.svg)](https://www.nuget.org/packages/v8-v140_xp-x86/)|
|V8 x86 for Visual Studio 2017 XP platform toolset|[![NuGet](https://img.shields.io/nuget/v/v8-v141_xp-x86.svg)](https://www.nuget.org/packages/v8-v141_xp-x86/)|
|V8 x64 for Visual Studio 2013 XP platform toolset|[![NuGet](https://img.shields.io/nuget/v/v8-v120_xp-x64.svg)](https://www.nuget.org/packages/v8-v120_xp-x64/)|
|V8 x64 for Visual Studio 2015 XP platform toolset|[![NuGet](https://img.shields.io/nuget/v/v8-v140_xp-x64.svg)](https://www.nuget.org/packages/v8-v140_xp-x64/)|
|V8 x64 for Visual Studio 2017 XP platform toolset|[![NuGet](https://img.shields.io/nuget/v/v8-v141_xp-x64.svg)](https://www.nuget.org/packages/v8-v141_xp-x64/)|


## Usage

To use V8 in a project install the package `v8-$PlatformToolset-$Platform.$Version`
from a console with `nuget install` command or from inside of Visual Studio
(see menu option *Tools -> NuGet Package Manager -> Manage NuGet Packages for Solution...*)
where

  * `$PlatformToolset` is the C++ toolset version used in Visual Studio:
    * `v120` - for Visual Studio 2013
    * `v140` - for Visual Studio 2015
    * `v141` - for Visual Studio 2017
    * `v120_xp` - for Visual Studio 2013 XP platform toolset
    * `v140_xp` - for Visual Studio 2015 XP platform toolset
    * `v141_xp` - for Visual Studio 2017 XP platform toolset
  
  * `$Platform` is a target platform type, currently `x86` or `x64`.

  * `$Version` is the actual V8 version, one of https://chromium.googlesource.com/v8/v8.git/+refs

There are 3 package kinds:

  * `v8-$PlatformToolset-$Platform.$Version` - contains developer header and 
    library files; depends on `v8.redist` package

  * `v8.redist-$PlatformToolset-$Platform.$Version` - prebuilt V8 binaries:
    dlls, blobs, etc.

  * `v8.symbols-$PlatformToolset-$Platform.$Version` - debug symbols for V8:
    [pdb files](https://en.wikipedia.org/wiki/Program_database)

After successful packages installation add `#include <v8.h>` in a C++  project
and build it. All necessary files (*.lib, *.dll, *.pdb) would be referenced
in the project automatically with MsBuild property sheets.


## How to build

This section is mostly for the package maintainers who wants to update V8.

Tools required to build V8 NuGet package on Windows:

  * Visual C++ toolset (version >=2013)
  * Python 2.X
  * Git
  * NuGet (https://dist.nuget.org/index.html)

To build V8 and make NuGet packages:

  1. Run `build.py` with optional command-line arguments.
  2. Publish `nuget/*.nupkg` files after successful build.
  
Build script `build.py` supports command-line arguments to specify package build options:

  1. V8 version branch/tag name (or `V8_VERSION` environment variable), default is `lkgr` branch
  2. Target platform (or `PLATFORM` evnironment variable), default is [`x86`, `x64`]
  3. Configuration (or `CONFIGURATION` environment variable), default is [`Debug`, `Release`]
  4. XP platofrm toolset usage flag (or `XP` environment variable), default is not set
