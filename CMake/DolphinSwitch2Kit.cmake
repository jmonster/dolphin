# Optional host input only. Disabled builds do not require Swift or change deployment targets.
option(ENABLE_SWITCH2KIT "Enable native Switch 2 controllers on macOS 15+" OFF)
if(NOT ENABLE_SWITCH2KIT)
  return()
endif()
if(NOT APPLE OR NOT ENABLE_SDL OR NOT ENABLE_QT)
  message(FATAL_ERROR "Switch2Kit requires macOS and the SDL and Qt backends")
endif()
if(NOT CMAKE_OSX_DEPLOYMENT_TARGET OR CMAKE_OSX_DEPLOYMENT_TARGET VERSION_LESS 15.0)
  message(FATAL_ERROR "Switch2Kit requires -DCMAKE_OSX_DEPLOYMENT_TARGET=15.0 or newer")
endif()
set(_switch2kit_source "${PROJECT_SOURCE_DIR}/Externals/Switch2Kit")
if(NOT EXISTS "${_switch2kit_source}/Integrations/SDL3/CMakeLists.txt")
  message(FATAL_ERROR "Initialize the Switch2Kit submodule: git submodule update --init Externals/Switch2Kit")
endif()
add_subdirectory("${_switch2kit_source}/Integrations/SDL3" "${PROJECT_BINARY_DIR}/switch2kit")
target_sources(inputcommon PRIVATE
  ControllerInterface/SDL/Switch2Kit.cpp
  ControllerInterface/SDL/Switch2Kit.h
)
target_link_libraries(inputcommon PRIVATE Switch2Kit::SDL3)
target_compile_definitions(inputcommon PUBLIC HAVE_SWITCH2KIT)
