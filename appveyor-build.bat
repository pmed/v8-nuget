if "%APPVEYOR_BUILD_WORKER_IMAGE%" == "Visual Studio 2017" (
  call vswhere_usability_wrapper.cmd
  call "%VCINSTALLDIR%\Auxiliary\Build\vcvarsall.bat" %PLATFORM%
  set VisualStudioVersion=15.0
)
if "%APPVEYOR_BUILD_WORKER_IMAGE%" == "Visual Studio 2015" (
  call "%ProgramFiles(x86)%\Microsoft Visual Studio 14.0\VC\vcvarsall.bat" %PLATFORM%
)

python build.py
nuget push *.nupkg %NUGET_API_KEY% -Source https://nuget.org/